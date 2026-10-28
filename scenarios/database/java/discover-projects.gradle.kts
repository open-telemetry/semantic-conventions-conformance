import java.nio.file.FileVisitResult
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.SimpleFileVisitor
import java.nio.file.attribute.BasicFileAttributes

val excludedDirectoryNames = setOf("bin", "build", "buildSrc", "node_modules", "out", "src", "target")
val projectDirectories = mutableSetOf<String>()
val rootPath = rootDir.toPath()

Files.walkFileTree(
    rootPath,
    object : SimpleFileVisitor<Path>() {
        override fun preVisitDirectory(
            dir: Path,
            attrs: BasicFileAttributes,
        ): FileVisitResult {
            if (
                dir != rootPath &&
                (
                    dir.fileName.toString() in excludedDirectoryNames ||
                        dir.fileName.toString().startsWith(".") ||
                        Files.exists(dir.resolve("settings.gradle")) ||
                        Files.exists(dir.resolve("settings.gradle.kts"))
                )
            ) {
                return FileVisitResult.SKIP_SUBTREE
            }
            return FileVisitResult.CONTINUE
        }

        override fun visitFile(
            file: Path,
            attrs: BasicFileAttributes,
        ): FileVisitResult {
            if (file.fileName.toString() in setOf("build.gradle", "build.gradle.kts")) {
                val directory = rootPath.relativize(file.parent).joinToString(":")
                if (directory.isNotEmpty()) {
                    projectDirectories.add(directory)
                }
            }
            return FileVisitResult.CONTINUE
        }
    },
)

projectDirectories.sorted().forEach { include(it) }
