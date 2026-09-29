
#include "my_options.h"

MyOptions::MyOptions(std::string app_description, std::string app_name)
    : App(app_description, app_name)
{
    add_option("-o, --oriantation", mult_oriantation,
               "choose between output stationary, or weight stationary")
        ->transform(CLI::CheckedTransformer(oriantation_map, CLI::ignore_case));

    add_option("-m, --matrix-height", m, "choose matrix height dimantion");
    add_option("-k, --inner-dimantion", k, "choose inner dimantion");
    add_option("-n, --matrix-width", n, "choose matrix width dimantion");

    add_option("-p, --small-percision", small_percision,
               "choose percision of low percision matrix")
        ->check(CLI::IsMember({1, 2, 4, 8}));

    add_option(
        "-r, --ratio", ratio,
        "choose ratio between low and high percision elements (high / low)")
        ->check([this](const std::string& input) {
            int input_int = std::atoi(input.c_str());
            if (this->small_percision * input_int <= 8) {
                return std::string("");
            }
            std::string ret = "Ratio must keep the high percision matrix at "
                              "percision smaller than 8 bytes. Try: ";
            int sp          = this->small_percision;
            int r           = 1;
            do {
                sp *= r;
                ret += std::to_string(r);
                if (sp < 8) {
                    ret += " or";
                }
                ret += " ";
                r += 1;
            } while (sp < 8);
            ret += "instead :)";
            return ret;
        });

    add_option("--fc, --fifo-capacity", capacity, "choose fifo capacity");

    add_option("--fg, --fifo-gencost", generation_cost,
               "choose fifo generation cost");

    add_option("--fa, --fifo-access", accsess_cost,
               "choose access cost for elements of the prng fifo");

    add_option("-s, --seed-size", seed_size, "choose percision of the seeds")
        ->check(CLI::IsMember({1, 2, 4, 8}));

    add_option("--th, --tile-height", tile_h, "choose height of tiles")
        ->check([this](const std::string& input) {
            if (std::atoi(input.c_str()) <= this->m) {
                return std::string("");
            }
            std::string ret =
                "tile height must be smaller than matrix height: ";
            ret += std::to_string(this->m);
            return ret;
        });

    add_option("--tw, --tile-width", tile_w, "choose width of tiles")
        ->check([this](const std::string& input) {
            if (std::atoi(input.c_str()) <= this->n) {
                return std::string("");
            }
            std::string ret = "tile width must be smaller than matrix width: ";
            ret += std::to_string(this->n);
            return ret;
        });

    add_option("--rd, --reg-dim", reg_dim, "choose register tile dimension");
    add_option("--mc, --mulacc-cost", mulacc_cost,
               "choose cycles per multiply-accumulate operation");

    add_option("-B, --BSource", b_source,
               "Choose B elemnt source between memory or prng fifo")
        ->transform(CLI::CheckedTransformer(b_source_map, CLI::ignore_case));

    add_option("-c, --cache", cache_options,
               "set cache options in units of log2 [ block_size, "
               "mem_cycles, l1_size, l1_cycles, "
               "l1_assoc, l2_size, l2_cycles, l2_assoc ]");

    add_flag("-w, --write-allocate, --no-write-allocate{false}", write_alloc,
             "set write allocate");
}

void MyOptions::apply_config(const Config& config)
{
    m               = config.m;
    k               = config.k;
    n               = config.n;
    small_percision = config.small_percision;
    ratio           = config.ratio;

    block_size  = config.block_size;
    mem_cycles  = config.mem_cycles;
    l1_size     = config.l1_size;
    l1_cycles   = config.l1_cycles;
    l1_assoc    = config.l1_assoc;
    l2_size     = config.l2_size;
    l2_cycles   = config.l2_cycles;
    l2_assoc    = config.l2_assoc;
    write_alloc = config.write_alloc;

    capacity        = config.capacity;
    generation_cost = config.generation_cost;
    accsess_cost    = config.accsess_cost;
    seed_size       = config.seed_size;

    tile_w      = config.tile_w;
    tile_h      = config.tile_h;
    b_source    = config.b_source;
    reg_dim     = config.reg_dim;
    mulacc_cost = config.mulacc_cost;
}

void MyOptions::post_parse()
{
    if (get_option("-c")->count() > 0) {
        block_size = cache_options[0];
        mem_cycles = cache_options[1];
        l1_size    = cache_options[2];
        l1_cycles  = cache_options[3];
        l1_assoc   = cache_options[4];
        l2_size    = cache_options[5];
        l2_cycles  = cache_options[6];
        l2_assoc   = cache_options[7];
    }
}
