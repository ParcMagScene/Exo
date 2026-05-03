#ifndef FLOORPLANENUMS_H
#define FLOORPLANENUMS_H

#include <QObject>
#include <QtQml/qqml.h>

namespace FloorPlan {
Q_NAMESPACE
QML_ELEMENT

enum class ItemType {
    Wall,
    Door,
    Window,
    Room,
    Furniture,
    Device,
    Camera,
    Sensor
};
Q_ENUM_NS(ItemType)

} // namespace FloorPlan

#endif // FLOORPLANENUMS_H
