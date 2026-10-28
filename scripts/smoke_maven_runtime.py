#!/usr/bin/env python3
"""Opt-in CI smoke with an actual Maven distribution and tiny Java 17 project.

Downloads only the pinned project's Maven/plugins/JUnit into the managed test
cache. Never reads or changes the user's application or Kanban state.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher-dir", type=Path, default=ROOT / "scripts")
    parser.add_argument(
        "--extension-source-root", type=Path, default=ROOT / "scripts/maven-output-extension",
        help="Directory containing the Maven output lifecycle extension sources",
    )
    parser.add_argument("--verifier", type=Path, default=ROOT / "scripts/verification/maven_verification.py")
    parser.add_argument("--version", choices=("3.6.3", "3.9.9"), default="3.6.3")
    args = parser.parse_args()
    extension_root = args.extension_source_root.resolve()
    for filename in ("HermesOutputLifecycleParticipant.java", "components.xml"):
        source = extension_root / filename
        if not source.is_file() or not os.access(source, os.R_OK):
            parser.error(f"Maven output extension source is missing or unreadable: {source}")
    java = Path(os.environ["JAVA_HOME"])
    assert (java / "bin/javac").is_file(), java
    launcher = args.launcher_dir / "hermes-maven"
    bridge = args.launcher_dir / "hermes-java"
    assert os.access(launcher, os.X_OK) and os.access(bridge, os.X_OK)
    spec = importlib.util.spec_from_file_location("verification", args.verifier)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    with tempfile.TemporaryDirectory(prefix="devkit-maven-smoke-") as tmp:
        root = Path(tmp)
        project = root / "project"
        home = root / "default-home"
        project.mkdir()
        home.mkdir()
        cache = root / "maven"
        os.environ["HOME"] = str(home)
        for key in list(os.environ):
            if key.startswith("HERMES_MAVEN_"):
                os.environ.pop(key)
        os.environ["HERMES_MAVEN_ROOT"] = str(cache)
        # The checkout test uses source files; the Docker compatibility test uses installed image files.
        os.environ["HERMES_MAVEN_OUTPUT_EXTENSION_SOURCE_ROOT"] = str(extension_root)
        # Any fallback to system mvn must fail, even on hosted runners with Maven.
        bad_bin = root / "no-system-maven"
        bad_bin.mkdir()
        (bad_bin / "mvn").write_text("#!/bin/sh\necho SYSTEM_MAVEN_FALLBACK >&2\nexit 97\n")
        (bad_bin / "mvn").chmod(0o755)
        os.environ["PATH"] = str(bad_bin) + os.pathsep + os.environ["PATH"]
        (project / ".hermes").mkdir()
        (project / ".hermes/toolchain.env").write_text("JAVA_HOME=" + shlex.quote(str(java)) + "\n")
        props = project / ".mvn/wrapper/maven-wrapper.properties"
        props.parent.mkdir(parents=True)
        props.write_bytes((f"distributionUrl=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/{args.version}/apache-maven-{args.version}-bin.zip\r\n").encode())
        wrapper = project / "mvnw"
        wrapper.write_bytes(b"#!/bin/sh\r\nexit 96\r\n")
        wrapper.chmod(0o644)
        before_wrapper = wrapper.read_bytes()
        (project / "pom.xml").write_text('''<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion><groupId>example</groupId><artifactId>devkit-smoke</artifactId><version>1</version>
  <properties><maven.compiler.release>17</maven.compiler.release><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties>
  <dependencies><dependency><groupId>junit</groupId><artifactId>junit</artifactId><version>4.13.2</version><scope>test</scope></dependency></dependencies>
  <build><plugins>
    <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.11.0</version></plugin>
    <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.2.5</version></plugin>
    <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-resources-plugin</artifactId><version>3.3.1</version>
      <executions>
        <execution><id>relocate-relative-generated-sources</id><phase>generate-sources</phase>
          <goals><goal>copy-resources</goal></goals>
          <configuration>
            <outputDirectory>target/generated-sources/java</outputDirectory>
            <resources><resource><directory>src/generated-fixture</directory></resource></resources>
          </configuration>
        </execution>
      </executions>
    </plugin>
  </plugins></build>
</project>\n''')
        production = project / "src/main/java/example/Answer.java"
        test = project / "src/test/java/example/AnswerTest.java"
        production.parent.mkdir(parents=True)
        test.parent.mkdir(parents=True)
        production.write_text("package example; public record Answer(int value) {}\n")
        test.write_text("package example; import org.junit.Test; import static org.junit.Assert.*; public class AnswerTest { @Test public void returnsAnswer() { assertEquals(42, new Answer(42).value()); } }\n")
        generated_fixture = project / "src/generated-fixture/Generated.java"
        generated_fixture.parent.mkdir(parents=True)
        generated_fixture.write_text("package example; public class Generated {}\n")
        # An existing source-mounted target must not be overwritten, augmented or deleted.
        source_target = project / "target"
        source_target.mkdir()
        existing_output = source_target / "existing-user-file.txt"
        existing_output.write_bytes(b"keep original target untouched")
        # No Git repo is needed for an acknowledged Non-Git workspace.
        probe = subprocess.run([str(launcher), "--diagnose", "./mvnw"], cwd=project, text=True, capture_output=True, timeout=10)
        assert probe.returncode == 0 and "PREPARATION_REQUIRED" in probe.stdout, probe
        assert not cache.exists(), "read-only diagnose created cache state"
        version = subprocess.run([str(bridge), "./mvnw", "--version"], cwd=project, text=True, capture_output=True, timeout=240)
        assert version.returncode == 0, version.stderr
        assert f"Apache Maven {args.version}" in version.stdout, version.stdout
        for command in (["-B", "-DskipTests", "compile"], ["-B", "-Dtest=AnswerTest", "test"], ["-o", "-B", "-Dtest=AnswerTest", "test"]):
            result = verifier.verify(project, "./mvnw", command, launcher, cache / "verification", 300)
            if result["status"] != "PASS":
                print(Path(result["log"]).read_text()[-20000:])
                raise AssertionError(result)
            print(f"PASS: Maven {args.version} {' '.join(command)}; elapsed={result['elapsed_seconds']}")
        # Original source target must never be touched; Maven extensions relocate
        # both compilation and reports under the persistent Linux-only cache.
        assert existing_output.read_bytes() == b"keep original target untouched"
        assert sorted(source_target.rglob("*")) == [existing_output], "Maven wrote into the source worktree target"
        generated = list((cache / "builds").rglob("generated-sources/java/Generated.java"))
        assert len(generated) == 1 and generated[0].read_text() == generated_fixture.read_text(), generated
        classes = list((cache / "builds").rglob("classes/example/Answer.class"))
        reports = list((cache / "builds").rglob("surefire-reports/TEST-example.AnswerTest.xml"))
        assert len(classes) == 1, classes
        assert len(reports) == 1 and 'failures="0"' in reports[0].read_text(), reports
        assert (cache / "repository/junit/junit/4.13.2/junit-4.13.2.jar").is_file()
        assert not (home / ".m2").exists(), "Maven wrote an unmanaged HOME cache"
        assert wrapper.read_bytes() == before_wrapper, "project Wrapper was modified"

        # Reactor modules must not share output directories or mutate module targets.
        (project / "pom.xml").write_text((project / "pom.xml").read_text().replace(
            "<properties>", "<packaging>pom</packaging><modules><module>module</module></modules><properties>", 1
        ))
        module = project / "module"
        module.mkdir()
        (module / "pom.xml").write_text('''<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent><groupId>example</groupId><artifactId>devkit-smoke</artifactId><version>1</version></parent>
  <artifactId>module</artifactId>
  <build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.11.0</version></plugin></plugins></build>
</project>''')
        sample = module / "src/main/java/example/Module.java"
        sample.parent.mkdir(parents=True)
        sample.write_text("package example; public class Module { public int value() { return 42; } }")
        reactor = verifier.verify(project, "./mvnw", ["-B", "-pl", "module", "-am", "test-compile"], launcher, cache / "verification", 300)
        if reactor["status"] != "PASS":
            print(Path(reactor["log"]).read_text()[-20000:])
            raise AssertionError(reactor)
        assert not (module / "target").exists(), "Maven wrote module output into source"
        built = list((cache / "builds").rglob("module/target/classes/example/Module.class"))
        assert len(built) == 1, built
        assert existing_output.read_bytes() == b"keep original target untouched"
        assert sorted(source_target.rglob("*")) == [existing_output], "Reactor modified source target"
        # An output path escaping target must fail before Maven writes there.
        unsafe = (project / "pom.xml").read_text().replace(
            "<outputDirectory>target/generated-sources/java</outputDirectory>",
            "<outputDirectory>target/../../unsafe-generated-output</outputDirectory>", 1,
        )
        (project / "pom.xml").write_text(unsafe)
        blocked = subprocess.run([str(launcher), "./mvnw", "-B", "compile"], cwd=project,
                                 text=True, capture_output=True, timeout=240)
        assert blocked.returncode != 0 and "MAVEN_OUTPUT_LAYOUT_UNSUPPORTED" in (
            blocked.stdout + blocked.stderr
        ), blocked.stderr
        assert not (root / "unsafe-generated-output").exists()
        assert existing_output.read_bytes() == b"keep original target untouched"
        print("PASS: Maven relative generated-sources redirected outside source; pre-existing target preserved; unsafe output blocked; Maven "
              + args.version + " JUnit/offline/reactor")


if __name__ == "__main__":
    main()
