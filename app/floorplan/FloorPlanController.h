#ifndef FLOORPLANCONTROLLER_H
#define FLOORPLANCONTROLLER_H

#include "FloorPlanModel.h"

#include <QObject>
#include <QPointF>
#include <QRectF>
#include <QVariantMap>
#include <QList>
#include <QString>
#include <QtQml/qqml.h>

// ─────────────────────────────────────────────────────
//  UndoAction — single undo/redo entry
// ─────────────────────────────────────────────────────
struct UndoAction
{
    enum Type { Add, Remove, Move, Rotate, Update };
    Type        type;
    QString     itemId;
    QVariantMap before;   // state before action
    QVariantMap after;    // state after action
};

// ─────────────────────────────────────────────────────
//  FloorPlanController — bridge between QML and Model
//
//  Manages:
//   • DAO tool state machine
//   • Undo/redo stack (C++ side)
//   • Multi-dwelling plan management
//   • Begin/update/end action protocol for drawing tools
//   • Advanced alignment helpers
//
//  Thread: main thread only (QML-bound).
// ─────────────────────────────────────────────────────
class FloorPlanController : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(FloorPlanModel* model   READ model   WRITE setModel   NOTIFY modelChanged)
    Q_PROPERTY(QString currentTool     READ currentTool WRITE setTool NOTIFY toolChanged)
    Q_PROPERTY(bool    canUndo         READ canUndo  NOTIFY undoStateChanged)
    Q_PROPERTY(bool    canRedo         READ canRedo  NOTIFY undoStateChanged)
    Q_PROPERTY(int     undoCount       READ undoCount NOTIFY undoStateChanged)
    Q_PROPERTY(int     redoCount       READ redoCount NOTIFY undoStateChanged)
    Q_PROPERTY(QStringList selectedIds READ selectedIds WRITE setSelectedIds NOTIFY selectionChanged)
    Q_PROPERTY(bool    actionInProgress READ actionInProgress NOTIFY actionInProgressChanged)

    // ── Multi-dwelling ──
    Q_PROPERTY(QStringList planFiles   READ planFiles NOTIFY planFilesChanged)
    Q_PROPERTY(QString     currentPlanPath READ currentPlanPath NOTIFY currentPlanPathChanged)

public:
    explicit FloorPlanController(QObject *parent = nullptr);
    ~FloorPlanController() override = default;

    // ── model ──
    FloorPlanModel *model() const { return m_model; }
    void setModel(FloorPlanModel *m);

    // ── tool ──
    QString currentTool() const { return m_currentTool; }

    // ── undo/redo ──
    bool canUndo() const { return !m_undoStack.isEmpty(); }
    bool canRedo() const { return !m_redoStack.isEmpty(); }
    int  undoCount() const { return m_undoStack.size(); }
    int  redoCount() const { return m_redoStack.size(); }

    // ── selection ──
    QStringList selectedIds() const { return m_selectedIds; }
    void setSelectedIds(const QStringList &ids);

    // ── action state ──
    bool actionInProgress() const { return m_actionInProgress; }

    // ── multi-dwelling ──
    QStringList planFiles() const { return m_planFiles; }
    QString currentPlanPath() const { return m_currentPlanPath; }

    // ══════════════════════════════════════════════
    //  Q_INVOKABLE — QML API
    // ══════════════════════════════════════════════

    // ── tool ──
    Q_INVOKABLE void setTool(const QString &tool);

    // ── action protocol (drawing tools) ──
    Q_INVOKABLE void beginAction(qreal x, qreal y);
    Q_INVOKABLE void updateAction(qreal x, qreal y);
    Q_INVOKABLE QString endAction(qreal x, qreal y);
    Q_INVOKABLE void cancelAction();

    // ── undo/redo ──
    Q_INVOKABLE void undo();
    Q_INVOKABLE void redo();
    Q_INVOKABLE void clearUndoHistory();

    // ── selection ──
    Q_INVOKABLE void selectItem(const QString &id, bool addToSelection = false);
    Q_INVOKABLE void deselectItem(const QString &id);
    Q_INVOKABLE void selectRect(qreal x, qreal y, qreal w, qreal h, bool addToSelection = false);
    Q_INVOKABLE void selectAll();
    Q_INVOKABLE void deselectAll();
    Q_INVOKABLE void deleteSelected();

    // ── item ops (with undo) ──
    Q_INVOKABLE QString createItemWithUndo(const QString &type, const QVariantMap &data);
    Q_INVOKABLE void deleteItemWithUndo(const QString &id);
    Q_INVOKABLE void moveItemWithUndo(const QString &id, qreal x, qreal y);
    Q_INVOKABLE void rotateItemWithUndo(const QString &id, qreal angle);
    Q_INVOKABLE void updateItemWithUndo(const QString &id, const QVariantMap &data);

    // ── snapping ──
    Q_INVOKABLE QPointF applySnap(QPointF p) const;
    Q_INVOKABLE QVariantMap findAlignmentGuides(QPointF p, qreal w = 0, qreal h = 0) const;

    // ── multi-dwelling ──
    Q_INVOKABLE void newPlan(const QString &name = QString());
    Q_INVOKABLE void openPlan(const QString &path);
    Q_INVOKABLE void savePlan(const QString &path = QString());
    Q_INVOKABLE void scanPlanFiles(const QString &directory = QStringLiteral("config"));

    // ── rotation convenience ──
    Q_INVOKABLE void applyRotation(const QString &id, qreal angle);

    // ── device linking ──
    Q_INVOKABLE void linkDevice(const QString &itemId, const QString &deviceId);
    Q_INVOKABLE void unlinkDevice(const QString &itemId);
    Q_INVOKABLE QString linkedDeviceForItem(const QString &itemId) const;
    Q_INVOKABLE QVariantMap deviceInfoForItem(const QString &itemId) const;

signals:
    void modelChanged();
    void toolChanged();
    void undoStateChanged();
    void selectionChanged();
    void actionInProgressChanged();
    void planFilesChanged();
    void currentPlanPathChanged();

    // ── action signals for QML Canvas ──
    void actionStarted(const QString &tool, qreal x, qreal y);
    void actionUpdated(qreal x, qreal y);
    void actionFinished(const QString &itemId);
    void actionCancelled();

    // ── device linking signals ──
    void deviceLinked(const QString &itemId, const QString &deviceId);
    void deviceUnlinked(const QString &itemId);

private:
    void pushUndo(UndoAction::Type type, const QString &itemId,
                  const QVariantMap &before, const QVariantMap &after);
    void applyAction(const UndoAction &action, bool isUndo);

    QVariantMap defaultDataForTool(const QString &tool) const;

    FloorPlanModel          *m_model = nullptr;
    QString                  m_currentTool = QStringLiteral("select");
    QList<UndoAction>        m_undoStack;
    QList<UndoAction>        m_redoStack;
    QStringList              m_selectedIds;
    bool                     m_actionInProgress = false;

    // ── action state ──
    QPointF  m_actionOrigin;
    QString  m_actionPreviewId;  // temp item during drawing

    // ── multi-dwelling ──
    QStringList m_planFiles;
    QString     m_currentPlanPath;

    // ── device links (itemId → deviceId) ──
    QHash<QString, QString> m_deviceLinks;

    static constexpr int MAX_UNDO_DEPTH = 200;
};

#endif // FLOORPLANCONTROLLER_H
