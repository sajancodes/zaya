plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.zaya.companion"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.zaya.companion"
        minSdk = 26
        targetSdk = 36
        versionCode = providers.environmentVariable("ZAYA_VERSION_CODE").orElse("4").get().toInt()
        versionName = providers.environmentVariable("ZAYA_VERSION_NAME").orElse("0.4.0").get()
    }

    sourceSets {
        // The owner's character art lives in mobile/android/assets so it can be
        // dropped in without touching the app module. Missing files fall back to
        // the bundled crop of the desktop assets.
        getByName("main").assets.srcDirs("src/main/assets", "assets")
    }

    signingConfigs {
        create("updates") {
            storeFile = file(providers.environmentVariable("ZAYA_SIGNING_STORE").orElse(
                System.getProperty("user.home") + "/.android/debug.keystore").get())
            storePassword = providers.environmentVariable("ZAYA_STORE_PASSWORD").orElse("android").get()
            keyAlias = providers.environmentVariable("ZAYA_KEY_ALIAS").orElse("androiddebugkey").get()
            keyPassword = providers.environmentVariable("ZAYA_KEY_PASSWORD").orElse("android").get()
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("updates")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}", "/META-INF/versions/9/OSGI-INF/MANIFEST.MF")
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.process)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.core)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.coroutines.android)

    debugImplementation(libs.androidx.compose.ui.tooling)

}
