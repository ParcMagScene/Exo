// app/utils/SafeIO.h — header-only helpers to remove silent failures.
//
// Goals:
//   * mkpath() returns bool that is silently ignored across the codebase
//     → ensureDir() logs a warning and returns the bool.
//   * QWebSocket::sendTextMessage() returns the number of bytes sent (or -1)
//     and is also silently ignored → wsSafeSend() logs and returns the result.
//
// These helpers are header-only (inline) and pull only Qt headers already
// transitively included by their callers, so no CMake change is required.

#pragma once

#include "core/LogManager.h"

#include <QDir>
#include <QFileInfo>
#include <QString>
#include <QWebSocket>

namespace exo::safeio {

// Create the directory tree for `dirPath`. Logs a warning if creation fails.
// Returns true if the directory exists (already or after creation).
inline bool ensureDir(const QString &dirPath, const char *context = "ensureDir")
{
    if (dirPath.isEmpty())
        return false;
    QDir d;
    if (d.exists(dirPath))
        return true;
    if (d.mkpath(dirPath))
        return true;
    hWarning(exoMain) << context << ": mkpath failed for" << dirPath;
    return false;
}

// Convenience overload: ensure the parent directory of a file path exists.
inline bool ensureParentDir(const QString &filePath, const char *context = "ensureParentDir")
{
    return ensureDir(QFileInfo(filePath).absolutePath(), context);
}

// Send `payload` over `ws`. Logs a warning if the socket is null/closed
// or sendTextMessage returns -1. Returns the bytes-sent value (<=0 on error).
inline qint64 wsSafeSend(QWebSocket *ws, const QString &payload, const char *context = "wsSend")
{
    if (!ws) {
        hWarning(exoMain) << context << ": null websocket, payload dropped"
                          << payload.left(80);
        return -1;
    }
    if (ws->state() != QAbstractSocket::ConnectedState) {
        hWarning(exoMain) << context << ": socket not connected (state="
                          << int(ws->state()) << "), payload dropped"
                          << payload.left(80);
        return -1;
    }
    const qint64 sent = ws->sendTextMessage(payload);
    if (sent < 0) {
        hWarning(exoMain) << context << ": sendTextMessage returned" << sent
                          << "for payload" << payload.left(80);
    }
    return sent;
}

} // namespace exo::safeio
