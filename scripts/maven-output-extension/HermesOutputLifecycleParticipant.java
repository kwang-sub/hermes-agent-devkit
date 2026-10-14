package dev.hermes.maven;

import java.io.File;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Locale;
import org.apache.maven.AbstractMavenLifecycleParticipant;
import org.apache.maven.MavenExecutionException;
import org.apache.maven.execution.MavenSession;
import org.apache.maven.model.Build;
import org.apache.maven.model.Plugin;
import org.apache.maven.model.PluginExecution;
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

        // Maven plugins may contain absolute or module-relative output paths.
        // Rewrite only paths inside the original build tree, never the source tree.
        rewritePlugins(project, build.getPlugins(), basedir, oldBuild, newBuild);
        PluginManagement management = build.getPluginManagement();
        if (management != null) {
            rewritePlugins(project, management.getPlugins(), basedir, oldBuild, newBuild);
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

    private static void rewritePlugins(MavenProject project, List<Plugin> plugins,
                                       Path basedir, Path oldBuild, Path newBuild)
            throws MavenExecutionException {
        if (plugins == null) {
            return;
        }
        for (Plugin plugin : plugins) {
            if (plugin.getConfiguration() instanceof Xpp3Dom) {
                rewriteDom(project, (Xpp3Dom) plugin.getConfiguration(), basedir, oldBuild, newBuild);
            }
            if (plugin.getExecutions() != null) {
                for (PluginExecution execution : plugin.getExecutions()) {
                    if (execution.getConfiguration() instanceof Xpp3Dom) {
                        rewriteDom(project, (Xpp3Dom) execution.getConfiguration(), basedir, oldBuild, newBuild);
                    }
                }
            }
        }
    }

    private static void rewriteDom(MavenProject project, Xpp3Dom node,
                                   Path basedir, Path oldBuild, Path newBuild)
            throws MavenExecutionException {
        String value = node.getValue();
        if (value != null) {
            String relocated = relocatePluginPath(project, node.getName(), value, basedir, oldBuild, newBuild);
            if (relocated != null) {
                node.setValue(relocated);
            }
        }
        for (Xpp3Dom child : node.getChildren()) {
            rewriteDom(project, child, basedir, oldBuild, newBuild);
        }
    }

    /**
     * Maven File parameters resolve relative to each reactor module's basedir.
     * Only relocate complete paths within the original build directory: never
     * replace a textual substring or redirect a normal src/ path.
     */
    private static String relocatePluginPath(MavenProject project, String nodeName, String rawValue,
                                             Path basedir, Path oldBuild, Path newBuild)
            throws MavenExecutionException {
        String value = rawValue.trim();
        if (value.isEmpty()) {
            return null;
        }
        boolean outputNode = isOutputLocation(nodeName);

        // A still-unexpanded build-directory expression must refer to the NEW
        // build tree even when Maven evaluates plugin parameters after this hook.
        String buildExpression = "${project.build.directory}";
        if (value.equals(buildExpression) || value.startsWith(buildExpression + "/")) {
            String suffix = value.substring(buildExpression.length());
            if (suffix.contains("${") || suffix.contains("\\") || suffix.contains("\n")
                    || suffix.contains("\r")) {
                throw failure(project, "MAVEN_OUTPUT_LAYOUT_UNSUPPORTED: dynamic build output expression: " + nodeName);
            }
            Path result = newBuild.resolve("." + suffix).normalize();
            if (!result.startsWith(newBuild)) {
                throw failure(project, "MAVEN_OUTPUT_LAYOUT_UNSUPPORTED: build output escapes Linux root: " + nodeName);
            }
            return result.toString();
        }
        if (value.contains("${") || value.contains("\n") || value.contains("\r")) {
            if (outputNode) {
                throw failure(project, "MAVEN_OUTPUT_LAYOUT_UNSUPPORTED: unresolved output path: " + nodeName);
            }
            return null;
        }
        // Backslashes are not path separators on Linux. Do not silently accept
        // a Windows-style output that could create a file under /workspace.
        if (outputNode && value.indexOf('\\') >= 0) {
            throw failure(project, "MAVEN_OUTPUT_LAYOUT_UNSUPPORTED: non-Linux output path: " + nodeName);
        }
        Path path;
        try {
            path = Paths.get(value);
        } catch (InvalidPathException exception) {
            if (outputNode) {
                throw failure(project, "MAVEN_OUTPUT_LAYOUT_UNSUPPORTED: invalid output path: " + nodeName);
            }
            return null;
        }

        // 'target' may also be ordinary metadata (e.g. a classifier). Only
        // bare paths in an output field, or paths with a separator, qualify.
        if (!path.isAbsolute() && value.indexOf('/') < 0 && !outputNode) {
            return null;
        }
        Path resolved = (path.isAbsolute() ? path : basedir.resolve(path)).toAbsolutePath().normalize();
        if (resolved.startsWith(oldBuild)) {
            return newBuild.resolve(oldBuild.relativize(resolved)).toString();
        }
        // The extension cannot guarantee source preservation for explicit
        // plugin output locations outside the managed build tree.
        if (outputNode && !resolved.startsWith(newBuild)) {
            throw failure(project, "MAVEN_OUTPUT_LAYOUT_UNSUPPORTED: plugin " + nodeName
                    + " outside original build directory: " + resolved);
        }
        return null;
    }

    private static boolean isOutputLocation(String name) {
        switch (name.toLowerCase(Locale.ROOT)) {
            case "outputdirectory":
            case "testoutputdirectory":
            case "outputdir":
            case "outputfile":
            case "destinationdirectory":
            case "destinationfile":
            case "generatedsourcesdirectory":
            case "generatedtestsourcesdirectory":
            case "reportsdirectory":
            case "reportoutputdirectory":
                return true;
            default:
                return false;
        }
    }

    private static MavenExecutionException failure(MavenProject project, String message) {
        return new MavenExecutionException(message, project.getFile());
    }
}
