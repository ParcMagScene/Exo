#pragma once

#include <QString>

class AIMemoryManager;

class AssistantPromptBuilder
{
public:
    static QString buildSystemContext(AIMemoryManager *memoryManager);
};
