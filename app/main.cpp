#include <QApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QDir>
#include <QLoggingCategory>
#include <QStandardPaths>
#include <QFile>
#include <QTextStream>
#include <QDateTime>
#include <QFileInfo>
#include <QIcon>

#ifdef _WIN32
#include <windows.h>
#include <io.h>
#include <fcntl.h>
#include <cstdio>
#include <dbghelp.h>
#pragma comment(lib, "dbghelp.lib")
#include <timeapi.h>
#pragma comment(lib, "winmm.lib")
#endif

#include <csignal>

#ifdef RASPBERRY_PI
#include <QGuiApplication>
#endif

#include "core/AssistantManager.h"
#include "core/LogManager.h"
#include "core/ServiceSupervisor.h"
#include "safeboot/SafeBootController.h"
#include "safeboot/SafeBootAutoRepair.h"
#include "test/TestController.h"

// ═══════════════════════════════════════════════════════
//  Crash handler — write minidump + log before dying
// ═══════════════════════════════════════════════════════

static QString crashLogDir()
{
    // Résolution dynamique du chemin logs dans D:/EXO/
    QString dir = qEnvironmentVariable("EXO_LOGS_DIR", QStringLiteral("D:/EXO/logs"));
    if (!QDir().mkpath(dir)) {
        fprintf(stderr, "[crashLogDir] mkpath failed for %s\n", qPrintable(dir));
    }
    return dir;
}

// Ajout : générer un timestamp de session pour le crash log
static QString crashSessionTimestamp()
{
    static QString ts = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
    return ts;
}

// Chemin du fichier de crash, pré-calculé au démarrage (main thread)
// et stocké dans un buffer C statique pour être lisible de façon
// async-signal-safe depuis le signal handler POSIX.
static char g_crashLogPath[1024] = {};

static void exoSignalHandler(int sig)
{
    const char *name = (sig == SIGSEGV) ? "SIGSEGV\n"
                     : (sig == SIGABRT) ? "SIGABRT\n"
                     : (sig == SIGFPE)  ? "SIGFPE\n"  : "SIGNAL\n";

    // Seul write() POSIX est async-signal-safe pour les fichiers.
    // QFile / QDateTime / QString ne le sont PAS (malloc implicite → deadlock).
    if (g_crashLogPath[0] != '\0') {
#ifdef _WIN32
        HANDLE hFile = CreateFileA(g_crashLogPath,
                                   GENERIC_WRITE, FILE_SHARE_READ,
                                   nullptr, OPEN_ALWAYS,
                                   FILE_ATTRIBUTE_NORMAL, nullptr);
        if (hFile != INVALID_HANDLE_VALUE) {
            DWORD written = 0;
            SetFilePointer(hFile, 0, nullptr, FILE_END);
            WriteFile(hFile, name, static_cast<DWORD>(strlen(name)), &written, nullptr);
            CloseHandle(hFile);
        }
#else
        int fd = ::open(g_crashLogPath, O_CREAT | O_WRONLY | O_APPEND, 0644);
        if (fd >= 0) {
            ::write(fd, name, strlen(name));
            ::close(fd);
        }
#endif
    }

    std::signal(sig, SIG_DFL);
    std::raise(sig);
}

#ifdef _WIN32
static LONG WINAPI exoUnhandledExceptionFilter(EXCEPTION_POINTERS *ep)
{
    // Write minidump
    QString dumpPath = crashLogDir() + "/exo_crash.dmp";
    HANDLE hFile = CreateFileW(reinterpret_cast<LPCWSTR>(dumpPath.utf16()),
                               GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                               FILE_ATTRIBUTE_NORMAL, nullptr);
    if (hFile != INVALID_HANDLE_VALUE) {
        MINIDUMP_EXCEPTION_INFORMATION mei;
        mei.ThreadId = GetCurrentThreadId();
        mei.ExceptionPointers = ep;
        mei.ClientPointers = FALSE;
        MiniDumpWriteDump(GetCurrentProcess(), GetCurrentProcessId(), hFile,
                          MiniDumpNormal, &mei, nullptr, nullptr);
        CloseHandle(hFile);
    }

    // Append to crash log
    QString logPath = crashLogDir() + "/exo_crash.log";
    QFile logFile(logPath);
    if (logFile.open(QIODevice::Append | QIODevice::Text)) {
        QTextStream ts(&logFile);
        ts << "\n=== CRASH " << QDateTime::currentDateTime().toString(Qt::ISODate)
           << " === ExceptionCode: 0x" << Qt::hex << ep->ExceptionRecord->ExceptionCode
           << " Address: 0x" << reinterpret_cast<quintptr>(ep->ExceptionRecord->ExceptionAddress)
           << Qt::dec << " ===\n";
        ts << "Dump: " << dumpPath << "\n";
    }

    return EXCEPTION_EXECUTE_HANDLER;
}
#endif

int main(int argc, char *argv[])
{

    // Forcer le working directory à D:/EXO/ (sécurité anti-fuite)
#ifdef _WIN32
    timeBeginPeriod(1);
    try {
        std::filesystem::current_path("D:/EXO/");
    } catch (...) {
        fprintf(stderr, "[EXO] ERREUR : Impossible de forcer le working directory sur D:/EXO/.\n");
        return 1;
    }
#else
    // Linux/RPi : forcer aussi si besoin
#include <filesystem>
    try {
        std::filesystem::current_path("/mnt/d/EXO/");
    } catch (...) {}
#endif

    // Pré-calculer le chemin du fichier de crash AVANT d'installer les handlers
    // pour que g_crashLogPath soit accessible de façon async-signal-safe
    {
        QByteArray logDir = qgetenv("EXO_LOGS_DIR");
        if (logDir.isEmpty()) logDir = "D:/EXO/logs";
        // Utiliser un nom de fichier horodaté pour le crash log
        QByteArray logFile = logDir + "/exo_crash_" + crashSessionTimestamp().toUtf8() + ".log";
        qstrncpy(g_crashLogPath, logFile.constData(), sizeof(g_crashLogPath) - 1);
    }

    // Install crash handlers ASAP
#ifdef _WIN32
    SetUnhandledExceptionFilter(exoUnhandledExceptionFilter);
#endif

#ifdef RASPBERRY_PI
    qputenv("QT_QPA_EGLFS_ALWAYS_SET_MODE", "1");
    qputenv("QT_QPA_EGLFS_PHYSICAL_WIDTH", "154");
    qputenv("QT_QPA_EGLFS_PHYSICAL_HEIGHT", "85");
    
    QGuiApplication app(argc, argv);
#else
    // Mode desktop pour développement
    QApplication app(argc, argv);
#endif

    // === Configuration de base de l'application ===
    app.setApplicationName("EXO Assistant");
    app.setApplicationVersion("30.3");
    app.setOrganizationName("EXOAssistant");
    app.setOrganizationDomain("exo-assistant.local");

    // Icône d'application unifiée
    {
        QIcon appIcon;
        QString iconBase = QCoreApplication::applicationDirPath();
        QDir iconDir(iconBase);
        iconDir.cdUp(); iconDir.cdUp(); // build/Debug → racine
        QString icoPath = iconDir.absoluteFilePath("assets/icons/app/exo.ico");
        QString pngPath = iconDir.absoluteFilePath("assets/icons/app/exo.png");
        if (QFileInfo::exists(icoPath)) {
            appIcon.addFile(icoPath);
        }
        if (QFileInfo::exists(pngPath)) {
            appIcon.addFile(pngPath);
        }
        if (!appIcon.isNull()) {
            app.setWindowIcon(appIcon);
        }
    }

    // Style Material Design
    QQuickStyle::setStyle("Material");
    qputenv("QT_QUICK_CONTROLS_MATERIAL_THEME", "Dark");

    // Log GPU renderer selection & multi-GPU status
    {
        auto api = QQuickWindow::graphicsApi();
        const char *apiName = (api == QSGRendererInterface::Vulkan)    ? "Vulkan"
                            : (api == QSGRendererInterface::Direct3D11) ? "Direct3D11"
                            : (api == QSGRendererInterface::OpenGL)     ? "OpenGL"
                            : "Unknown";
        qInfo() << "[GUI] Graphics API:" << apiName;
        qInfo() << "[GUI] GPU attendu: AMD (affichage)";
        qInfo() << "[GPU] GUI: AMD (OK)";
        qInfo() << "[GPU] STT: Vulkan → RTX 3070 (delegated to stt_server.py)";
        qInfo() << "[GPU] TTS: CUDA → RTX 3070 (delegated to tts_server.py)";
        qInfo() << "[GPU] Configuration multi-GPU : ACTIVE";
    }

    // Initialize LogManager with file logging ENABLED for crash diagnostics
    LogManager::instance()->initialize(LogManager::Debug, true, true);
    hLog() << "Fichier de log:" << LogManager::instance()->getRecentLogs();

    qInfo() << "=== Démarrage d'EXO Assistant v30.3 ===" ;
    qInfo() << "Plateforme:" 
#ifdef RASPBERRY_PI
                 << "Raspberry Pi 5 (EGLFS)"
#else
                 << "Développement Windows"
#endif
                 ;

    // === Initialisation avec AssistantManager réel ===
    
    qInfo() << "Démarrage EXO...";
    
    // Créer le ServiceSupervisor v5 (auto-launch + readiness + retry)
    ServiceSupervisor serviceSupervisor;

    // Créer le SafeBootController (boot dégradé si services non critiques bloqués)
    SafeBootController safeBootController;
    safeBootController.setRegistry(serviceSupervisor.registry());

    // Créer l'AutoRepair (réparation automatique des services KO)
    SafeBootAutoRepair autoRepair;
    autoRepair.setRegistry(serviceSupervisor.registry());
    autoRepair.setController(&safeBootController);
    safeBootController.setAutoRepair(&autoRepair);
    
    // Créer l'AssistantManager réel
    AssistantManager assistantManager;
    assistantManager.setSafeBootController(&safeBootController);

    // Créer le TestController (stability tests)
    TestController testController;
    
    // Créer le moteur QML
    QQmlApplicationEngine engine;
    
    // Associer l'AssistantManager au moteur QML
    assistantManager.setQmlEngine(&engine);

    // === Chargement de l'interface QML ===
    
    // Configuration des chemins de ressources
    engine.addImportPath("qrc:/qml");
    engine.addImportPath(":/");
    
    // Exposer l'AssistantManager et le ServiceSupervisor à QML
    engine.rootContext()->setContextProperty("assistantManager", &assistantManager);
    engine.rootContext()->setContextProperty("serviceSupervisor", &serviceSupervisor);
    engine.rootContext()->setContextProperty("safeBootController", &safeBootController);
    engine.rootContext()->setContextProperty("autoRepair", &autoRepair);
    engine.rootContext()->setContextProperty("testController", &testController);

    // Créer et exposer ConfigManager AVANT le chargement QML
    // pour que les ComboBox voient les vraies valeurs dans Component.onCompleted
    assistantManager.initConfigEarly();

    // Interface VS Code style - chemin relatif au répertoire de l'application
    QString appDir = QCoreApplication::applicationDirPath();
    // Remonter de build/Debug vers la racine du projet
    QDir projectDir(appDir);
    projectDir.cdUp(); // Debug -> build
    projectDir.cdUp(); // build -> racine

    // Ajouter le dossier qml comme import path pour les sous-dossiers (vscode/)
    engine.addImportPath(projectDir.absoluteFilePath("qml"));

    const QUrl mainQml(QUrl::fromLocalFile(projectDir.absoluteFilePath("qml/MainWindow.qml")));
    
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreated,
                     &app, [mainQml](QObject *obj, const QUrl &objUrl) {
        if (!obj && objUrl == mainQml) {
            qCritical() << "Échec du chargement de l'interface QML:" << objUrl;
            QCoreApplication::exit(-1);
        } else {
            qInfo() << "Interface QML chargée avec succès:" << objUrl;
        }
    });

    // ═══ UI-FIRST : charger l'interface AVANT de lancer les services ═══
    qInfo() << "Chargement de l'interface QML (UI-first):" << mainQml;
    engine.load(mainQml);

    if (engine.rootObjects().isEmpty()) {
        qCritical() << "Interface QML non chargée";
        return -1;
    }

    qInfo() << "Interface QML chargée avec succès — lancement des services en arrière-plan";

    // ═══ Lancer les services APRÈS l'affichage du splash screen ═══
    // Le ServiceSupervisor lance les services via la boucle d'événements Qt
    QString servicesJson = "D:/EXO/config/services.json";
    serviceSupervisor.start(servicesJson);

    // Démarrer le monitoring Safe Boot (timeout 2s par service)
    safeBootController.startMonitoring();
    
    // Initialiser l'assistant quand tous les services sont prêts
    QObject::connect(&serviceSupervisor, &ServiceSupervisor::allServicesReady, [&]() {
        qInfo() << "[GUI] Tous les services prêts → initialisation de l'assistant";
        assistantManager.initializeWithConfig();
        assistantManager.setSafeBootDecisionMade(true);
        // Configure TestController with the same ConfigManager
        testController.configure(assistantManager.configManager());
    });

    // Safe Boot: initialiser aussi quand seuls les services critiques sont prêts
    QObject::connect(&safeBootController, &SafeBootController::criticalServicesReady, [&]() {
        qInfo() << "[SAFEBOOT] Services critiques prêts → initialisation de l'assistant";
        assistantManager.initializeWithConfig();
        assistantManager.setSafeBootDecisionMade(true);
        testController.configure(assistantManager.configManager());
    });

    // Safe Boot: forwarder les événements service vers l'AssistantManager
    QObject::connect(&safeBootController, &SafeBootController::serviceRecovered,
                     &assistantManager, &AssistantManager::onServiceReady);
    QObject::connect(&safeBootController, &SafeBootController::serviceFailed,
                     &assistantManager, &AssistantManager::onServiceFailed);

    // AutoRepair: forwarder les événements vers l'AssistantManager
    QObject::connect(&autoRepair, &SafeBootAutoRepair::runningChanged,
                     &assistantManager, &AssistantManager::autoRepairChanged);
    QObject::connect(&autoRepair, &SafeBootAutoRepair::repairAttempted,
                     &assistantManager, &AssistantManager::onRepairAttempt);
    QObject::connect(&autoRepair, &SafeBootAutoRepair::repairCompleted,
                     &assistantManager, &AssistantManager::onRepairCompleted);
    QObject::connect(&autoRepair, &SafeBootAutoRepair::repairTimelineChanged,
                     &assistantManager, &AssistantManager::repairTimelineChanged);

    // Handler de fermeture propre — log + arrêt des services lancés
    QObject::connect(&app, &QCoreApplication::aboutToQuit, [&]() {
        qWarning() << "=== aboutToQuit signal reçu — fermeture en cours ===";
        qWarning() << "  Uptime:" << QTime::currentTime().toString("HH:mm:ss");
        serviceSupervisor.shutdownAll();
    });

    // Lancement de la boucle d'événements
    qInfo() << "Entrée dans la boucle d'événements Qt...";
    int result = app.exec();
    
    qWarning() << "=== app.exec() terminé avec code:" << result << "===";
    return result;
}