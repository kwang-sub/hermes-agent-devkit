package dev.hermes.maven;

import java.io.File;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import org.apache.maven.AbstractMavenLifecycleParticipant;
import org.apache.maven.MavenExecutionException;
import org.apache.maven.execution.MavenSession;
import org.apache.maven.model.Build;
import org.apache.maven.model.Plugin;
import org.apache.maven.model.PluginManagement;
import org.apache.maven.model.Reporting;
import org.apache.maven.project.MavenProject;
import org.codehaus.plexus.util.xml.Xpp3Dom;

/** Redirects Maven generated output while leaving the original project and POM untouched. */
public final class HermesOutputLifecycleParticipant extends AbstractMavenLifecycleParticipant {
    @Override
    public void afterProjectsRead(MavenSession session) throws MavenExecutionException {
        String workspaceVariable = System.getenv("HERMES_MAVEN_SOURCE_ROOT");
        String outputVariable = System.getenv("HERMES_MAVEN_BUILD_DIR");
        if (workspaceVariable == null || outputVariable == null) {
            throw new MavenExecutionException("MAVEN_OUTPUT_ISOLATION_MISSING: managed launcher environment missing", (File) null);
        }
        Path workspace = Paths.get(workspaceVariable).toAbsolutePath().normalize();
        Path root = Paths.get(outputVariable).toAbsolutePath().normalize();
        if (!workspace.isAbsolute() || !root.isAbsolute() || root.startsWith(workspace)) {
            throw new MavenExecutionException("MAVEN_OUTPUT_ISOLATION_INVALID: output must be outside the source workspace", (File) null);
        }
        for (MavenProject project : session.getProjects()) {
            configure(project, workspace, root);
        }
    }

    private void configure(MavenProject project, Path workspace, Path root) throws MavenExecutionException {
        File basedirFile = project.getBasedir();
        if (basedirFile == null) {
            throw failure(project, "MAVEN_OUTPUT_ISOLATION_INVALID: missing project basedir");
        }
        Path basedir = basedirFile.toPath().toAbsolutePath().normalize();
        if (!basedir.startsWith(workspace)) {
            throw failure(project, "MAVEN_OUTPUT_ISOLATION_INVALID: reactor module escapes source workspace: " + basedir);
        }
        Build build = project.getBuild();
        if (build == null || build.getDirectory() == null || build.getDirectory().trim().isEmpty()) {
            throw failure(project, "MAVEN_OUTPUT_ISOLATION_INVALID: missing build directory");
        }
        Path oldBuild = resolve(basedir, build.getDirectory());
        Path newBuild = root.resolve(workspace.relativize(basedir)).resolve("target").normalize();
        if (!newBuild.startsWith(root)) {
            throw failure(project, "MAVEN_OUTPUT_ISOLATION_INVALID: module output escapes internal root");
        }
        String output = relocated(project, basedir, oldBuild, newBuild, build.getOutputDirectory(), "outputDirectory");
        String testOutput = relocated(project, basedir, oldBuild, newBuild, build.getTestOutputDirectory(), "testOutputDirectory");
        build.setDirectory(newBuild.toString());
        build.setOutputDirectory(output);
        build.setTestOutputDirectory(testOutput);

        // Explicit plugin output paths interpolated by the model builder may still refer
        // to the original target; preserve their suffix without touching source directories.
        rewritePlugins(build.getPlugins(), oldBuild.toString(), newBuild.toString());
        PluginManagement management = build.getPluginManagement();
        if (management != null) {
            rewritePlugins(management.getPlugins(), oldBuild.toString(), newBuild.toString());
        }
        Reporting reporting = project.getModel().getReporting();
        if (reporting != null && reporting.getOutputDirectory() != null) {
            reporting.setOutputDirectory(relocated(project, basedir, oldBuild, newBuild,
                    reporting.getOutputDirectory(), "reporting.outputDirectory"));
        }
        System.out.println("HERMES_MAVEN_MODULE_OUTPUT=" + newBuild);
    }

    private static String relocated(MavenProject project, Path basedir, Path oldBuild, Path newBuild,
                                    String configured, String field) throws MavenExecutionException {
        if (configured == null || configured.trim().isEmpty()) {
            throw failure(project, "MAVEN_OUTPUT_ISOLATION_INVALID: empty " + field);
        }
        Path original = resolve(basedir, configured);
        if (!original.startsWith(oldBuild)) {
            throw failure(project, "MAVEN_OUTPUT_LAYOUT_UNSUPPORTED: " + field + " outside build directory: " + original);
        }
        return newBuild.resolve(oldBuild.relativize(original)).toString();
    }

    private static Path resolve(Path basedir, String value) {
        Path path = Paths.get(value);
        return (path.isAbsolute() ? path : basedir.resolve(path)).toAbsolutePath().normalize();
    }

    private static void rewritePlugins(List<Plugin> plugins, String oldBuild, String newBuild) {
        if (plugins == null) {
            return;
        }
        for (Plugin plugin : plugins) {
            if (plugin.getConfiguration() instanceof Xpp3Dom) {
                rewriteDom((Xpp3Dom) plugin.getConfiguration(), oldBuild, newBuild);
            }
            if (plugin.getExecutions() != null) {
                plugin.getExecutions().forEach(execution -> {
                    if (execution.getConfiguration() instanceof Xpp3Dom) {
                        rewriteDom((Xpp3Dom) execution.getConfiguration(), oldBuild, newBuild);
                    }
                });
            }
        }
    }

    private static void rewriteDom(Xpp3Dom node, String oldBuild, String newBuild) {
        String value = node.getValue();
        if (value != null && (value.equals(oldBuild) || value.startsWith(oldBuild + File.separator))) {
            node.setValue(newBuild + value.substring(oldBuild.length()));
        }
        for (Xpp3Dom child : node.getChildren()) {
            rewriteDom(child, oldBuild, newBuild);
        }
    }

    private static MavenExecutionException failure(MavenProject project, String message) {
        return new MavenExecutionException(message, project.getFile());
    }
}
