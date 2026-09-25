#include "registry.h"
#include <spdlog/spdlog.h>

Registry& gRegistry()
{
    static Registry registry{};
    return registry;
}
