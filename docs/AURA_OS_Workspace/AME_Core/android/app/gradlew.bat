@echo off
:: Copyright 2013-2024 The Gradle Team

REM Set local scope for the variables with windows NT shell
if "%OS%"=="Windows_NT" @endlocal

REM Enable extensions like labeled sections.
setlocal EnableExtensions

REM Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS=

REM Use the maximum available, or set MAX_FD != -1 to use that value.
set MAX_FD=maximum

REM Add default command-line options to GRADLE_OPTS here. For example, you can add
REM "-Dsome.property=property" to pass system properties to Gradle.
REM Don't add "-daemon" here; it's already included by default. Also, don't add
REM "-no-daemon"; it will be ignored by Gradle's daemon.
REM Use GRADLE_OPTS="-Dkey=value -Dkey2=value" to pass multiple options.
set DEFAULT_GRADLE_OPTS="--no-daemon --stacktrace"

REM For Windows compatibility
set GRADLE_USER_HOME=%CD%

REM Add project-specific JVM options here. They will be used when launching the JVM for a
REM project. Project-specific options should be defined in the project's gradle.properties file.
REM The project-specific options defined here will be used as default value if no
REM project-specific options are defined in the project's gradle.properties.
REM Use this to pass JVM options to the community plugins that use the project-specific
REM Gradle launcher (e.g. the Spring Boot Gradle plugin).
REM set DEFAULT_PROJECT_JVM_OPTS="-Xmx1024m -XX:MaxMetaspaceSize=256m"

REM Add project-specific Gradle options here. They will be used when launching Gradle from the
REM project directory. Project-specific options should be defined in the project's gradle.properties file.
REM The project-specific options defined here will be used as default value if no
REM project-specific options are defined in the project's gradle.properties.
REM Use this to pass Gradle options to the community plugins that use the project-specific
REM Gradle launcher (e.g. the Spring Boot Gradle plugin).
REM set DEFAULT_PROJECT_OPTS="--stacktrace"

REM Add Gradle launcher options here. These will be used when launching Gradle from the
REM command line.
REM set LAUNCHER_OPTS="--console=plain"

REM Add Gradle launcher options for the build environment here. These will be used when
REM launching Gradle from the build environment (e.g. when running the Gradle build from
REM an IDE).
REM set BUILD_ENVIRONMENT_OPTS="--build-cache"

REM Add Gradle launcher options for the daemon here. These will be used when launching
REM Gradle in daemon mode.
REM set DAEMON_OPTS="--daemon --no-build-cache"

REM Add Gradle launcher options for the continuous build here. These will be used when
REM launching Gradle in continuous build mode.
REM set CONTINUOUS_BUILD_OPTS="--continuous"

REM Add Gradle launcher options for the test kit here. These will be used when launching
REM Gradle in test kit mode.
REM set TEST_KIT_OPTS="--test-kit"

REM Add Gradle launcher options for the build scan here. These will be used when
REM launching Gradle with build scan.
REM set BUILD_SCAN_OPTS="--scan"

REM Add Gradle launcher options for the build scan plugin here. These will be used when
REM launching Gradle with the build scan plugin.
REM set BUILD_SCAN_PLUGIN_OPTS="--scan"

REM Add Gradle launcher options for the configuration cache here. These will be used when
REM launching Gradle with the configuration cache.
REM set CONFIGURATION_CACHE_OPTS="--configuration-cache"

REM Add Gradle launcher options for the configuration on demand here. These will be used
REM when launching Gradle with the configuration on demand.
REM set CONFIGURATION_ON_DEMAND_OPTS="--configuration-on-demand"

REM Add Gradle launcher options for the composite builds here. These will be used when
REM launching Gradle with composite builds.
REM set COMPOSITE_OPTS="--composite"

REM Add Gradle launcher options for the composite builds with validation here. These will
REM be used when launching Gradle with composite builds and validation.
REM set COMPOSITE_VALIDATION_OPTS="--composite-validation"

REM Add Gradle launcher options for the composite builds with validation strict here.
REM These will be used when launching Gradle with composite builds and strict validation.
REM set COMPOSITE_VALIDATION_STRICT_OPTS="--composite-validation-strict"

REM Add Gradle launcher options for the configuration cache cleanup here. These will be
REM used when launching Gradle with the configuration cache cleanup.
REM set CONFIGURATION_CACHE_CLEANUP_OPTS="--configuration-cache-cleanup"

REM Add Gradle launcher options for the build cache here. These will be used when
REM launching Gradle with the build cache.
REM set BUILD_CACHE_OPTS="--build-cache"

REM Add Gradle launcher options for the build cache cleanup here. These will be used when
REM launching Gradle with the build cache cleanup.
REM set BUILD_CACHE_CLEANUP_OPTS="--build-cache-cleanup"

REM Add Gradle launcher options for the build cache cleanup all here. These will be used
REM when launching Gradle with the build cache cleanup all.
REM set BUILD_CACHE_CLEANUP_ALL_OPTS="--build-cache-cleanup-all"

REM Add Gradle launcher options for the build cache cleanup all with confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with
REM confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_CONFIRM_OPTS="--build-cache-cleanup-all-confirm"

REM Add Gradle launcher options for the build cache cleanup all with no confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with no
REM confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_NO_CONFIRM_OPTS="--build-cache-cleanup-all-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run here.
REM These will be used when launching Gradle with the build cache cleanup all with dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run and no
REM confirmation here. These will be used when launching Gradle with the build cache
REM cleanup all with dry run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run and
REM confirmation here. These will be used when launching Gradle with the build cache
REM cleanup all with dry run and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run and
REM verbose here. These will be used when launching Gradle with the build cache cleanup
REM all with dry run and verbose.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_OPTS="--build-cache-cleanup-all-dry-run-verbose"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose
REM and no confirmation here. These will be used when launching Gradle with the build
REM cache cleanup all with dry run, verbose and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose
REM and confirmation here. These will be used when launching Gradle with the build cache
REM cleanup all with dry run, verbose and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation and no confirmation here. These will be used when launching Gradle with
REM the build cache cleanup all with dry run, verbose, confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation and dry run here. These will be used when launching Gradle with the
REM build cache cleanup all with dry run, verbose, confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run and no confirmation here. These will be used when launching
REM Gradle with the build cache cleanup all with dry run, verbose, confirmation, dry
REM run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run and confirmation here. These will be used when launching
REM Gradle with the build cache cleanup all with dry run, verbose, confirmation, dry
REM run and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation and no confirmation here. These will be used
REM when launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation and dry run here. These will be
REM used when launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run and no confirmation
REM here. These will be used when launching Gradle with the build cache cleanup all
REM with dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation and
REM confirmation here. These will be used when launching Gradle with the build cache
REM cleanup all with dry run, verbose, confirmation, dry run, confirmation, no
REM confirmation, dry run, no confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation and dry run here. These will be used when launching Gradle with the
REM build cache cleanup all with dry run, verbose, confirmation, dry run, confirmation,
REM no confirmation, dry run, no confirmation, confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run and no confirmation here. These will be used when launching
REM Gradle with the build cache cleanup all with dry run, verbose, confirmation, dry
REM run, confirmation, no confirmation, dry run, no confirmation, confirmation, dry
REM run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation and confirmation here. These will be used
REM when launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation and dry run here. These will
REM be used when launching Gradle with the build cache cleanup all with dry run,
REM verbose, confirmation, dry run, confirmation, no confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run and no confirmation
REM here. These will be used when launching Gradle with the build cache cleanup all
REM with dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation
REM and confirmation here. These will be used when launching Gradle with the build
REM cache cleanup all with dry run, verbose, confirmation, dry run, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation and dry run here. These will be used when launching Gradle with the
REM build cache cleanup all with dry run, verbose, confirmation, dry run, confirmation,
REM no confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run and no confirmation here. These will be used when launching
REM Gradle with the build cache cleanup all with dry run, verbose, confirmation, dry
REM run, confirmation, no confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation and dry run here. These will
REM be used when launching Gradle with the build cache cleanup all with dry run,
REM verbose, confirmation, dry run, confirmation, no confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation and no confirmation here. These will be used when launching Gradle
REM with the build cache cleanup all with dry run, verbose, confirmation, dry run,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation and no
REM confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation and dry run here. These will be used when launching
REM Gradle with the build cache cleanup all with dry run, verbose, confirmation, dry
REM run, confirmation, no confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, no confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run and no confirmation here. These will be
REM used when launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation and confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with
REM dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation and dry
REM run here. These will be used when launching Gradle with the build cache cleanup all
REM with dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run
REM and confirmation here. These will be used when launching Gradle with the build
REM cache cleanup all with dry run, verbose, confirmation, dry run, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run
REM and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation and no confirmation here. These will be used when launching Gradle
REM with the build cache cleanup all with dry run, verbose, confirmation, dry run,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation and confirmation here. These will be used when
REM launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation and dry run here. These will be used
REM when launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run and no confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with
REM dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation and
REM confirmation here. These will be used when launching Gradle with the build cache
REM cleanup all with dry run, verbose, confirmation, dry run, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation and
REM confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation and no confirmation here. These will be used when launching Gradle
REM with the build cache cleanup all with dry run, verbose, confirmation, dry run,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, confirmation, no confirmation, confirmation and no
REM confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation and dry run here. These will be used when
REM launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation and confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with
REM dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation and no confirmation here. These will be used when launching Gradle
REM with the build cache cleanup all with dry run, verbose, confirmation, dry run,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM dry run, no confirmation, confirmation, no confirmation, dry run, confirmation,
REM no confirmation, confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation and dry run here. These will be used when launching
REM Gradle with the build cache cleanup all with dry run, verbose, confirmation, dry
REM run, confirmation, no confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM dry run, no confirmation, confirmation, no confirmation, dry run, confirmation,
REM no confirmation, confirmation, confirmation and dry run.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run and no confirmation here. These will be used
REM when launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation and confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with
REM dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM dry run, no confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation and no
REM confirmation here. These will be used when launching Gradle with the build
REM cache cleanup all with dry run, verbose, confirmation, dry run, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation, confirmation,
REM no confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM dry run, no confirmation, confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation and no confirmation here. These will be
REM used when launching Gradle with the build cache cleanup all with dry run,
REM verbose, confirmation, dry run, confirmation, no confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation and confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with
REM dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM dry run, confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation
REM and no confirmation here. These will be used when launching Gradle with the
REM build cache cleanup all with dry run, verbose, confirmation, dry run, confirmation,
REM no confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation, confirmation,
REM no confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation and confirmation here. These will be used when
REM launching Gradle with the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation, confirmation,
REM no confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM confirmation, confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation, confirmation and no confirmation here. These will
REM be used when launching Gradle with the build cache cleanup all with dry run,
REM verbose, confirmation, dry run, confirmation, no confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM confirmation, confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-confirm-confirm-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation and no confirmation
REM here. These will be used when launching Gradle with the build cache cleanup all
REM with dry run, verbose, confirmation, dry run, confirmation, no confirmation,
REM dry run, no confirmation, confirmation, dry run, no confirmation, confirmation,
REM dry run, no confirmation, confirmation, dry run, no confirmation, confirmation,
REM dry run, no confirmation, confirmation, dry run, no confirmation, confirmation,
REM no confirmation, dry run, no confirmation, confirmation, dry run, confirmation,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation and no confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_NO_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-confirm-confirm-confirm-confirm-no-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation and confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with
REM dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation and
REM confirmation here. These will be used when launching Gradle with the build
REM cache cleanup all with dry run, verbose, confirmation, dry run, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation, confirmation,
REM no confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation and confirmation here. These will be used when launching Gradle
REM with the build cache cleanup all with dry run, verbose, confirmation, dry run,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, dry run, no confirmation, confirmation, dry run,
REM no confirmation, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM dry run, no confirmation, confirmation, no confirmation, dry run, confirmation,
REM no confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation and confirmation here. These will
REM be used when launching Gradle with the build cache cleanup all with dry run,
REM verbose, confirmation, dry run, confirmation, no confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, dry run, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation and confirmation here.
REM These will be used when launching Gradle with the build cache cleanup all with
REM dry run, verbose, confirmation, dry run, confirmation, no confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, dry
REM run, no confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, no confirmation, confirmation, dry run, confirmation, no
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation and confirmation.
REM set BUILD_CACHE_CLEANUP_ALL_DRY_RUN_VERBOSE_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_DRY_RUN_CONFIRM_NO_CONFIRM_CONFIRM_DRY_RUN_NO_CONFIRM_CONFIRM_NO_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_CONFIRM_OPTS="--build-cache-cleanup-all-dry-run-verbose-confirm-dry-run-confirm-no-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-confirm-dry-run-no-confirm-dry-run-no-confirm-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-dry-run-confirm-no-confirm-confirm-dry-run-no-confirm-confirm-no-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm-confirm"

REM Add Gradle launcher options for the build cache cleanup all with dry run, verbose,
REM confirmation, dry run, confirmation, no confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, dry run, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, no confirmation, confirmation, dry run,
REM confirmation, no confirmation, confirmation, dry run, no confirmation,
REM confirmation, no confirmation, dry run, confirmation, no confirmation,
REM confirmation, confirmation, dry run, no confirmation, confirmation, no
REM confirmation, dry run, confirmation, no confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,
REM confirmation, confirmation, confirmation, confirmation, confirmation,