#include "SimulationPropagation.h"

#include <QtMath>
#include <algorithm>
#include <queue>
#include <cmath>

// ═════════════════════════════════════════════════════
//  SimulationPropagation — Implémentation
// ═════════════════════════════════════════════════════

static const PropagationCell kEmptyCell;

SimulationPropagation::SimulationPropagation() = default;

void SimulationPropagation::initialize(int worldWidth, int worldHeight, int cellSize)
{
    m_worldW   = worldWidth;
    m_worldH   = worldHeight;
    m_cellSize = qMax(1, cellSize);
    m_gridW    = (worldWidth  + m_cellSize - 1) / m_cellSize;
    m_gridH    = (worldHeight + m_cellSize - 1) / m_cellSize;

    m_grid.resize(m_gridW);
    for (int x = 0; x < m_gridW; ++x) {
        m_grid[x].resize(m_gridH);
        for (int y = 0; y < m_gridH; ++y)
            m_grid[x][y] = PropagationCell{};
    }
}

void SimulationPropagation::setObstacles(const QVector<Obstacle> &obstacles)
{
    m_obstacles = obstacles;
    rasterizeObstacles();
}

void SimulationPropagation::addObstacle(const Obstacle &obs)
{
    m_obstacles.append(obs);
    // Rasterize just this one
    int x0 = qMax(0, toGridX(obs.rect.left()));
    int y0 = qMax(0, toGridY(obs.rect.top()));
    int x1 = qMin(m_gridW - 1, toGridX(obs.rect.right()));
    int y1 = qMin(m_gridH - 1, toGridY(obs.rect.bottom()));

    for (int gx = x0; gx <= x1; ++gx) {
        for (int gy = y0; gy <= y1; ++gy) {
            auto &cell = m_grid[gx][gy];
            if (obs.type == "wall" && obs.permeability < 0.1)
                cell.isObstacle = true;
            else if (obs.type == "door")
                cell.isDoor = true;
            else if (obs.type == "window")
                cell.isWindow = true;
        }
    }
}

void SimulationPropagation::clear()
{
    for (int x = 0; x < m_gridW; ++x) {
        for (int y = 0; y < m_gridH; ++y) {
            auto &c = m_grid[x][y];
            c.smokeLevel = 0.0;
            c.heatLevel  = 0.0;
            c.noiseLevel = 0.0;
            c.lightLevel = 0.0;
            c.waterLevel = 0.0;
        }
    }
}

bool SimulationPropagation::inBounds(int gx, int gy) const
{
    return gx >= 0 && gx < m_gridW && gy >= 0 && gy < m_gridH;
}

const PropagationCell &SimulationPropagation::cellAt(int gx, int gy) const
{
    if (!inBounds(gx, gy)) return kEmptyCell;
    return m_grid[gx][gy];
}

PropagationCell &SimulationPropagation::cellAt(int gx, int gy)
{
    return m_grid[gx][gy];
}

void SimulationPropagation::rasterizeObstacles()
{
    // Reset obstacle flags
    for (int x = 0; x < m_gridW; ++x)
        for (int y = 0; y < m_gridH; ++y)
            m_grid[x][y].isObstacle = false;

    for (const auto &obs : m_obstacles)
        addObstacle(obs); // re-add triggers rasterization
}

// ─────────────────────────────────────────────────────
//  Diffusion — Laplacien discret
// ─────────────────────────────────────────────────────

double SimulationPropagation::neighborAverage(const QVector<QVector<double>> &grid, int gx, int gy) const
{
    double sum = 0.0;
    int count = 0;
    static const int dx[] = {-1, 1, 0, 0};
    static const int dy[] = {0, 0, -1, 1};

    for (int d = 0; d < 4; ++d) {
        int nx = gx + dx[d];
        int ny = gy + dy[d];
        if (!inBounds(nx, ny)) continue;
        if (m_grid[nx][ny].isObstacle) continue;
        // Portes laissent passer partiellement
        double perm = m_grid[nx][ny].isDoor ? 0.4 : 1.0;
        sum += grid[nx][ny] * perm;
        count++;
    }
    return count > 0 ? sum / count : 0.0;
}

void SimulationPropagation::diffuseLayer(QVector<QVector<double>> &layer, double speed, double attenuation)
{
    // Create copy for read
    auto prev = layer;

    for (int x = 0; x < m_gridW; ++x) {
        for (int y = 0; y < m_gridH; ++y) {
            if (m_grid[x][y].isObstacle) continue;
            double avg = neighborAverage(prev, x, y);
            double val = prev[x][y];
            // Diffusion step
            double newVal = val + speed * (avg - val);
            // Attenuation
            newVal *= (1.0 - attenuation);
            layer[x][y] = qMax(0.0, newVal);
        }
    }
}

// ── Smoke ──

void SimulationPropagation::propagateSmoke(double speed, double attenuation)
{
    // Extract smoke layer
    QVector<QVector<double>> smokeLayer(m_gridW, QVector<double>(m_gridH, 0.0));
    for (int x = 0; x < m_gridW; ++x)
        for (int y = 0; y < m_gridH; ++y)
            smokeLayer[x][y] = m_grid[x][y].smokeLevel;

    diffuseLayer(smokeLayer, speed * 0.15, attenuation);

    for (int x = 0; x < m_gridW; ++x)
        for (int y = 0; y < m_gridH; ++y)
            m_grid[x][y].smokeLevel = smokeLayer[x][y];
}

// ── Heat ──

void SimulationPropagation::propagateHeat(double conductionRate, double convectionRate, double attenuation)
{
    QVector<QVector<double>> heatLayer(m_gridW, QVector<double>(m_gridH, 0.0));
    for (int x = 0; x < m_gridW; ++x)
        for (int y = 0; y < m_gridH; ++y)
            heatLayer[x][y] = m_grid[x][y].heatLevel;

    // Conduction (between adjacent)
    diffuseLayer(heatLayer, conductionRate * 0.1, 0.0);

    // Convection (slight upward drift — simulate by shifting -y bias)
    for (int x = 0; x < m_gridW; ++x) {
        for (int y = 1; y < m_gridH; ++y) {
            if (m_grid[x][y].isObstacle) continue;
            heatLayer[x][y - 1] += heatLayer[x][y] * convectionRate * 0.02;
        }
    }

    // Attenuation
    for (int x = 0; x < m_gridW; ++x)
        for (int y = 0; y < m_gridH; ++y)
            m_grid[x][y].heatLevel = qMax(0.0, heatLayer[x][y] * (1.0 - attenuation));
}

// ── Noise ──

void SimulationPropagation::propagateNoise(const QPointF &source, double intensity, double attenuation)
{
    int cx = toGridX(source.x());
    int cy = toGridY(source.y());

    for (int x = 0; x < m_gridW; ++x) {
        for (int y = 0; y < m_gridH; ++y) {
            if (m_grid[x][y].isObstacle) continue;
            double dx = x - cx;
            double dy = y - cy;
            double dist = std::sqrt(dx * dx + dy * dy);
            if (dist < 0.5) dist = 0.5;

            // 1/r² attenuation
            double level = intensity / (1.0 + dist * dist * attenuation);

            // Wall occlusion check (simple ray march)
            bool occluded = false;
            int steps = static_cast<int>(dist);
            for (int s = 1; s < steps; ++s) {
                double t = static_cast<double>(s) / steps;
                int mx = cx + static_cast<int>(dx * t);
                int my = cy + static_cast<int>(dy * t);
                if (inBounds(mx, my) && m_grid[mx][my].isObstacle) {
                    level *= 0.15; // heavy attenuation through walls
                    occluded = true;
                    break;
                }
            }

            m_grid[x][y].noiseLevel = qMax(m_grid[x][y].noiseLevel, level);
        }
    }
}

// ── Light ──

void SimulationPropagation::propagateLight(const QPointF &source, double angle, double fov, double intensity)
{
    int cx = toGridX(source.x());
    int cy = toGridY(source.y());

    double halfFov = fov * 0.5;
    double angleRad = qDegreesToRadians(angle);
    double halfFovRad = qDegreesToRadians(halfFov);
    int range = static_cast<int>(intensity * 8);

    for (int x = qMax(0, cx - range); x <= qMin(m_gridW - 1, cx + range); ++x) {
        for (int y = qMax(0, cy - range); y <= qMin(m_gridH - 1, cy + range); ++y) {
            if (m_grid[x][y].isObstacle) continue;

            double dx = x - cx;
            double dy = y - cy;
            double dist = std::sqrt(dx * dx + dy * dy);
            if (dist < 0.5) {
                m_grid[x][y].lightLevel = qMax(m_grid[x][y].lightLevel, intensity);
                continue;
            }

            // Check if within cone
            double toAngle = std::atan2(dy, dx);
            double diff = toAngle - angleRad;
            // Normalize to [-pi, pi]
            while (diff > M_PI) diff -= 2.0 * M_PI;
            while (diff < -M_PI) diff += 2.0 * M_PI;

            if (std::abs(diff) > halfFovRad) continue;

            // Distance attenuation
            double level = intensity / (1.0 + dist * 0.3);

            // Wall ray cast
            int steps = static_cast<int>(dist);
            for (int s = 1; s < steps; ++s) {
                double t = static_cast<double>(s) / steps;
                int mx = cx + static_cast<int>(dx * t);
                int my = cy + static_cast<int>(dy * t);
                if (inBounds(mx, my) && m_grid[mx][my].isObstacle) {
                    level = 0.0;
                    break;
                }
            }

            m_grid[x][y].lightLevel = qMax(m_grid[x][y].lightLevel, level);
        }
    }
}

// ── Water ──

void SimulationPropagation::propagateWater(double speed, double attenuation)
{
    QVector<QVector<double>> waterLayer(m_gridW, QVector<double>(m_gridH, 0.0));
    for (int x = 0; x < m_gridW; ++x)
        for (int y = 0; y < m_gridH; ++y)
            waterLayer[x][y] = m_grid[x][y].waterLevel;

    diffuseLayer(waterLayer, speed * 0.12, attenuation);

    for (int x = 0; x < m_gridW; ++x)
        for (int y = 0; y < m_gridH; ++y)
            m_grid[x][y].waterLevel = waterLayer[x][y];
}

// ── Inject ──

void SimulationPropagation::injectSmoke(const QPointF &worldPos, double amount)
{
    int gx = toGridX(worldPos.x());
    int gy = toGridY(worldPos.y());
    if (!inBounds(gx, gy) || m_grid[gx][gy].isObstacle) return;
    m_grid[gx][gy].smokeLevel = qMin(1.0, m_grid[gx][gy].smokeLevel + amount);
    // Spread to neighbors slightly
    for (int dx = -1; dx <= 1; ++dx) {
        for (int dy = -1; dy <= 1; ++dy) {
            int nx = gx + dx, ny = gy + dy;
            if (inBounds(nx, ny) && !m_grid[nx][ny].isObstacle)
                m_grid[nx][ny].smokeLevel = qMin(1.0, m_grid[nx][ny].smokeLevel + amount * 0.3);
        }
    }
}

void SimulationPropagation::injectHeat(const QPointF &worldPos, double amount)
{
    int gx = toGridX(worldPos.x());
    int gy = toGridY(worldPos.y());
    if (!inBounds(gx, gy) || m_grid[gx][gy].isObstacle) return;
    m_grid[gx][gy].heatLevel = qMin(1.0, m_grid[gx][gy].heatLevel + amount);
}

void SimulationPropagation::injectWater(const QPointF &worldPos, double amount)
{
    int gx = toGridX(worldPos.x());
    int gy = toGridY(worldPos.y());
    if (!inBounds(gx, gy) || m_grid[gx][gy].isObstacle) return;
    m_grid[gx][gy].waterLevel = qMin(1.0, m_grid[gx][gy].waterLevel + amount);
}

// ── Query ──

double SimulationPropagation::smokeLevelAt(const QPointF &worldPos) const
{
    int gx = toGridX(worldPos.x());
    int gy = toGridY(worldPos.y());
    if (!inBounds(gx, gy)) return 0.0;
    return m_grid[gx][gy].smokeLevel;
}

double SimulationPropagation::heatLevelAt(const QPointF &worldPos) const
{
    int gx = toGridX(worldPos.x());
    int gy = toGridY(worldPos.y());
    if (!inBounds(gx, gy)) return 0.0;
    return m_grid[gx][gy].heatLevel;
}

double SimulationPropagation::noiseLevelAt(const QPointF &worldPos) const
{
    int gx = toGridX(worldPos.x());
    int gy = toGridY(worldPos.y());
    if (!inBounds(gx, gy)) return 0.0;
    return m_grid[gx][gy].noiseLevel;
}

double SimulationPropagation::lightLevelAt(const QPointF &worldPos) const
{
    int gx = toGridX(worldPos.x());
    int gy = toGridY(worldPos.y());
    if (!inBounds(gx, gy)) return 0.0;
    return m_grid[gx][gy].lightLevel;
}

double SimulationPropagation::waterLevelAt(const QPointF &worldPos) const
{
    int gx = toGridX(worldPos.x());
    int gy = toGridY(worldPos.y());
    if (!inBounds(gx, gy)) return 0.0;
    return m_grid[gx][gy].waterLevel;
}

// ── Heatmap export ──

QVector<QVariantMap> SimulationPropagation::smokeHeatmap() const
{
    QVector<QVariantMap> result;
    for (int x = 0; x < m_gridW; ++x) {
        for (int y = 0; y < m_gridH; ++y) {
            double v = m_grid[x][y].smokeLevel;
            if (v > 0.01) {
                result.append({
                    {"x",     toWorldX(x)},
                    {"y",     toWorldY(y)},
                    {"value", v},
                    {"type",  "smoke"}
                });
            }
        }
    }
    return result;
}

QVector<QVariantMap> SimulationPropagation::heatHeatmap() const
{
    QVector<QVariantMap> result;
    for (int x = 0; x < m_gridW; ++x) {
        for (int y = 0; y < m_gridH; ++y) {
            double v = m_grid[x][y].heatLevel;
            if (v > 0.01) {
                result.append({
                    {"x",     toWorldX(x)},
                    {"y",     toWorldY(y)},
                    {"value", v},
                    {"type",  "heat"}
                });
            }
        }
    }
    return result;
}

QVector<QVariantMap> SimulationPropagation::waterHeatmap() const
{
    QVector<QVariantMap> result;
    for (int x = 0; x < m_gridW; ++x) {
        for (int y = 0; y < m_gridH; ++y) {
            double v = m_grid[x][y].waterLevel;
            if (v > 0.01) {
                result.append({
                    {"x",     toWorldX(x)},
                    {"y",     toWorldY(y)},
                    {"value", v},
                    {"type",  "water"}
                });
            }
        }
    }
    return result;
}

// ═════════════════════════════════════════════════════
//  Pathfinding A*
// ═════════════════════════════════════════════════════

QVector<QPointF> SimulationPropagation::findPath(const QPointF &from, const QPointF &to) const
{
    int sx = toGridX(from.x()), sy = toGridY(from.y());
    int ex = toGridX(to.x()),   ey = toGridY(to.y());

    if (!inBounds(sx, sy) || !inBounds(ex, ey))
        return {};

    // Open set as priority queue
    auto cmp = [](const PathNode &a, const PathNode &b) { return a.fCost() > b.fCost(); };
    std::priority_queue<PathNode, std::vector<PathNode>, decltype(cmp)> open(cmp);

    QVector<QVector<bool>>   closed(m_gridW, QVector<bool>(m_gridH, false));
    QVector<QVector<double>> gCosts(m_gridW, QVector<double>(m_gridH, 1e18));
    QVector<QVector<int>>    parentX(m_gridW, QVector<int>(m_gridH, -1));
    QVector<QVector<int>>    parentY(m_gridW, QVector<int>(m_gridH, -1));

    auto heuristic = [ex, ey](int x, int y) -> double {
        return std::sqrt(static_cast<double>((x - ex) * (x - ex) + (y - ey) * (y - ey)));
    };

    PathNode start;
    start.gx = sx; start.gy = sy;
    start.gCost = 0.0;
    start.hCost = heuristic(sx, sy);
    open.push(start);
    gCosts[sx][sy] = 0.0;

    static const int dx8[] = {-1, 1, 0, 0, -1, -1, 1, 1};
    static const int dy8[] = {0, 0, -1, 1, -1, 1, -1, 1};
    static const double cost8[] = {1.0, 1.0, 1.0, 1.0, 1.414, 1.414, 1.414, 1.414};

    bool found = false;

    while (!open.empty()) {
        PathNode cur = open.top();
        open.pop();

        if (cur.gx == ex && cur.gy == ey) {
            found = true;
            break;
        }

        if (closed[cur.gx][cur.gy]) continue;
        closed[cur.gx][cur.gy] = true;

        for (int d = 0; d < 8; ++d) {
            int nx = cur.gx + dx8[d];
            int ny = cur.gy + dy8[d];
            if (!inBounds(nx, ny)) continue;
            if (closed[nx][ny]) continue;
            if (m_grid[nx][ny].isObstacle) continue;

            double newG = gCosts[cur.gx][cur.gy] + cost8[d];
            if (newG < gCosts[nx][ny]) {
                gCosts[nx][ny]  = newG;
                parentX[nx][ny] = cur.gx;
                parentY[nx][ny] = cur.gy;

                PathNode next;
                next.gx = nx; next.gy = ny;
                next.gCost = newG;
                next.hCost = heuristic(nx, ny);
                open.push(next);
            }
        }
    }

    if (!found) return {};

    // Reconstruct path
    QVector<QPointF> path;
    int cx = ex, cy = ey;
    while (cx != sx || cy != sy) {
        path.prepend(QPointF(toWorldX(cx), toWorldY(cy)));
        int px = parentX[cx][cy];
        int py = parentY[cx][cy];
        cx = px;
        cy = py;
    }
    path.prepend(from);

    return path;
}
