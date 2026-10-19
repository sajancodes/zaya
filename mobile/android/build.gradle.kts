// Zaya's phone companion. One runtime: everything this app shows is produced by
// the Zaya process on the owner's laptop, which the phone reaches over the
// paired connection. Nothing here talks to any other backend.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
}
