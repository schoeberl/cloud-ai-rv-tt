scalaVersion := "2.13.18"
val chiselVersion = "7.16.0"
libraryDependencies += "org.chipsalliance" %% "chisel" % chiselVersion
addCompilerPlugin("org.chipsalliance" % "chisel-plugin" % chiselVersion cross CrossVersion.full)
scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls")
