#ifndef SIMULATIONPROPAGATION_H
#define SIMULATIONPROPAGATION_H

#include "SimulationEnums.h"
#include "SimulationEntity.h"

#include <QPointF>
#include <QRectF>
#include <QVector>
#include <QHash>
#include <QString>

// ─────────────────────────────────────────────────────
//  PropagationCell — Cellule de la grille de propagation
// ─────────────────────────────────────────────────────
struct PropagationCell
{
    double smokeLevel  = 0.0;
    double heatLevel   = 0.0;
    double noiseLevel  = 0.0;
    double lightLevel  = 0.0;
    double waterLevel  = 0.0;
    bool   isObstacle  = false;  // mur, meuble plein
    bool   isDoor      = false;
    bool   isWindow    = false;
    QString roomId;
};

// ─────────────────────────────────────────────────────
//  Obstacle — Pour le pathfinding et la propagation
// ─────────────────────────────────────────────────────
struct Obstacle
{
    QRectF rect;
    QString type;   // "wall", "door", "furniture"
    double permeability = 0.0;  // 0 = bloquant, 1 = transparent
};

// ─────────────────────────────────────────────────────
//  PathNode — Nœud A* pour le pathfinding
// ─────────────────────────────────────────────────────
struct PathNode
{
    int gx = 0;
    int gy = 0;
    double gCost  = 0.0;
    double hCost  = 0.0;
    double fCost() const { return gCost + hCost; }
    int parentX = -1;
    int parentY = -1;
};

// ─────────────────────────────────────────────────────
//  SimulationPropagation — Moteur de propagation
//
//  Grille 2D discrétisée du plan.  Modèles :
//    • Diffusion (fumée, gaz) : Laplacien discret
//    • Conduction (chaleur) : transfert mur→mur
//    • Convection (chaleur air) : diffusion + drift
//    • Atténuation (bruit) : 1/r² + obstacles
//    • Cônes (lumière) : projection géométrique
//    • FluidFlow (eau) : gravité + obstacles
//    • Pathfinding A* (trajectoires)
// ─────────────────────────────────────────────────────
class SimulationPropagation
{
public:
    SimulationPropagation();

    // ── Setup ──
    void initialize(int worldWidth, int worldHeight, int cellSize = 10);
    void setObstacles(const QVector<Obstacle> &obstacles);
    void addObstacle(const Obstacle &obs);
    void clear();

    // ── Grid access ──
    int gridWidth() const { return m_gridW; }
    int gridHeight() const { return m_gridH; }
    int cellSize() const { return m_cellSize; }
    const PropagationCell &cellAt(int gx, int gy) const;
    PropagationCell &cellAt(int gx, int gy);

    // World ↔ Grid conversion
    int toGridX(double worldX) const { return static_cast<int>(worldX / m_cellSize); }
    int toGridY(double worldY) const { return static_cast<int>(worldY / m_cellSize); }
    double toWorldX(int gx) const { return gx * m_cellSize + m_cellSize * 0.5; }
    double toWorldY(int gy) const { return gy * m_cellSize + m_cellSize * 0.5; }

    // ── Propagation step ──
    void propagateSmoke(double speed, double attenuation);
    void propagateHeat(double conductionRate, double convectionRate, double attenuation);
    void propagateNoise(const QPointF &source, double intensity, double attenuation);
    void propagateLight(const QPointF &source, double angle, double fov, double intensity);
    void propagateWater(double speed, double attenuation);

    // ── Inject values ──
    void injectSmoke(const QPointF &worldPos, double amount);
    void injectHeat(const QPointF &worldPos, double amount);
    void injectWater(const QPointF &worldPos, double amount);

    // ── Pathfinding A* ──
    QVector<QPointF> findPath(const QPointF &from, const QPointF &to) const;

    // ── Query ──
    double smokeLevelAt(const QPointF &worldPos) const;
    double heatLevelAt(const QPointF &worldPos) const;
    double noiseLevelAt(const QPointF &worldPos) const;
    double lightLevelAt(const QPointF &worldPos) const;
    double waterLevelAt(const QPointF &worldPos) const;

    // ── Heatmap export (for QML visualization) ──
    QVector<QVariantMap> smokeHeatmap() const;
    QVector<QVariantMap> heatHeatmap() const;
    QVector<QVariantMap> waterHeatmap() const;

private:
    bool inBounds(int gx, int gy) const;
    void rasterizeObstacles();
    double neighborAverage(const QVector<QVector<double>> &grid, int gx, int gy) const;
    void diffuseLayer(QVector<QVector<double>> &layer, double speed, double attenuation);

    int m_worldW   = 0;
    int m_worldH   = 0;
    int m_gridW    = 0;
    int m_gridH    = 0;
    int m_cellSize = 10;

    QVector<QVector<PropagationCell>> m_grid;
    QVector<Obstacle>                 m_obstacles;
};

#endif // SIMULATIONPROPAGATION_H
