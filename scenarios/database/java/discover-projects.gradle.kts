import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path

val excludedDirectoryNames = setOf("bin", "build", "buildSrc", "node_modules", "out", "src", "target")
val projectDirectories = mutableSetOf<String>()
val rootPath = rootDir.toPath()

fun discoverProjects(dir: Path) {
    val name = dir.fileName.toString()
    if (
        dir != rootPath &&
        (
            name in excludedDirectoryNames ||
                name.startsWith(".") ||
                Files.exists(dir.resolve("settings.gradle")) ||
                Files.exists(dir.resolve("settings.gradle.kts"))
        )
    ) {
        return
    }

    Files.newDirectoryStream(dir).use { entries ->
        for (file in entries) {
            if (Files.isDirectory(file, LinkOption.NOFOLLOW_LINKS)) {
                discoverProjects(file)
            } else if (file.fileName.toString() in setOf("build.gradle", "build.gradle.kts")) {
                val directory = rootPath.relativize(file.parent).joinToString(":")
                if (directory.isNotEmpty()) {
                    projectDirectories.add(directory)
                }
            }
        }
    }
}

discoverProjects(rootPath)
projectDirectories.sorted().forEach { include(it) }
