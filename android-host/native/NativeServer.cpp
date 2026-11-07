#include <jni.h>
#include <android/log.h>
#include <drogon/drogon.h>
#include <filesystem>
#include <string>
#include <stdexcept>

#include <gimuserver/db/MigrationManager.hpp>
#include <gimuserver/drogon/GimuServer.hpp>
#include <gimuserver/gme/common/BalanceSync.hpp>
#include <gimuserver/gme/common/GameDay.hpp>

// Reuse the full ORIGINAL SERVER, not stub endpoints or new game mechanics.
// JNI lives in an isolated :bfserver process because upstream changes cwd.
namespace {
    constexpr const char *TAG = "BF-Offline-Native";
    void failure(JNIEnv *env, const char *msg) {
        __android_log_print(ANDROID_LOG_ERROR, TAG, "%s", msg);
        jclass type = env->FindClass("java/lang/IllegalStateException");
        if (type) env->ThrowNew(type, msg);
    }
}

extern "C" JNIEXPORT void JNICALL
Java_com_domenklay_bfoffline_EmbeddedServerService_runNativeServer(
        JNIEnv *env, jclass, jstring jConfigPath) {
    if (!jConfigPath) { failure(env,"Missing server config"); return; }
    const char* chars = env->GetStringUTFChars(jConfigPath,nullptr);
    if (!chars) return;
    std::string path(chars);
    env->ReleaseStringUTFChars(jConfigPath,chars);
    try {
        auto config = std::filesystem::absolute(path);
        if (!std::filesystem::is_regular_file(config))
            throw std::runtime_error("Server config file missing");
        std::filesystem::current_path(config.parent_path());
        __android_log_print(ANDROID_LOG_INFO,TAG,"Starting upstream C++ server");
        drogon::app()
            .loadConfigFile(config.filename().string())
            .registerBeginningAdvice([]() {
                auto db = drogon::app().getDbClient();
                db->execSqlSync("PRAGMA busy_timeout = 10000;");
                db->execSqlSync("PRAGMA journal_mode = WAL;");
                db->execSqlSync("PRAGMA cache_size = -131072;");
                MigrationManager::RunMigrations(db);
                gme::loadDayShifts(db);
                gme::syncUnitStatBasis(db);
            }).run();
    } catch(const std::exception &e) {
        failure(env,e.what());
    } catch(...) {
        failure(env,"Unknown native server startup exception");
    }
}

extern "C" JNIEXPORT void JNICALL
Java_com_domenklay_bfoffline_EmbeddedServerService_stopNativeServer(
        JNIEnv*, jclass) {
    drogon::app().quit();
}
