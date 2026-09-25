#ifndef REGISTRY_H_
#define REGISTRY_H_

#include <algorithm>
#include <fmt/format.h>
#include <functional>
#include <type_traits>
#include <variant>
#include <vector>

class Registry
{
    friend Registry& gRegistry();

    using RegEntVar =
        std::variant<const uint32_t*, const size_t*, std::function<size_t()>,
                     std::function<double()>>;
    using RegEnt = std::pair<std::string, RegEntVar>;

  public:
    template <typename T>
    void reg_stat(const char* name, const T* stat)
    {
        entries_.emplace_back(RegEnt{name, RegEntVar{stat}});
    }

    template <typename T>
    void reg_stat(const char* name, std::function<T()> stat)
    {
        entries_.emplace_back(RegEnt{name, RegEntVar{stat}});
    }

    void dump()
    {
        std::sort(
            entries_.begin(), entries_.end(),
            [](const RegEnt& a, const RegEnt& b) { return a.first > b.first; });

        fmt::print("\n{:=^65}\n", " SIMULATION STATS ");
        fmt::print("{:<45} | {:>15}\n", "Metric", "Value");
        fmt::print("{:-^65}\n", "");

        for (const auto& ent : entries_) {
            std::visit(
                [&ent](auto&& arg) {
                    // because arg is a reference to a pointer
                    using t = std::decay_t<decltype(arg)>;
                    if constexpr (std::is_pointer_v<t>) {
                        fmt::print("{:<45} | {:>15}\n", ent.first, *arg);
                    } else {
                        fmt::print("{:<45} | {:>15}\n", ent.first, arg());
                    }
                },
                ent.second);
        }
        fmt::print("{:=^65}\n\n", "");
    }

  private:
    Registry() = default;

    std::vector<RegEnt> entries_;
};

Registry& gRegistry();

#endif
