#include "cache.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

using std::filesystem::path;

class Interpeter
{
  public:
    Interpeter(path input_file, simulator& cache_sim)
        : in_stream_(input_file), line_(0), cache_sim_(cache_sim)
    {
        if (!in_stream_.is_open()) {
            std::cerr << "error opening trace file" << std::endl;
            exit(1);
        }
    }

    Interpeter(const Interpeter&)            = delete;
    Interpeter& operator=(const Interpeter&) = delete;

    void run()
    {
        while (!in_stream_.eof()) {
            handleCmd();
        }
    }

  private:
    enum cmd {
        load_tile,
        move_tile,
        mul_acc,
        eof,
    };

    int line_;
    std::ifstream in_stream_;
    simulator& cache_sim_;

#define INTERPRETER_SYNTEX_CHECK(ch, missing, error_msg)                       \
    do {                                                                       \
        int cur = in_stream_.get();                                            \
        while (cur != ch) {                                                    \
            if (cur != ' ') {                                                  \
                std::cerr << "missing " missing " after " error_msg            \
                             " in line: "                                      \
                          << line_ << std::endl;                               \
                exit(1);                                                       \
            }                                                                  \
            cur = in_stream_.get();                                            \
        }                                                                      \
    } while (0)

    // ltea <Base Addr> <Width> <Height> <Stride> <Element Size> <Tile ID>
    void handleTload()
    {
        size_t base_addr;
        int tile_width;
        int tile_height;
        int stride;
        int elem_width;
        int dst_reg;

        INTERPRETER_SYNTEX_CHECK('(', "opening parenthesis", "command name");

        in_stream_ >> std::hex >> base_addr;
        INTERPRETER_SYNTEX_CHECK(',', "comma", "base address");

        in_stream_ >> std::dec >> tile_width;
        INTERPRETER_SYNTEX_CHECK(',', "comma", "tile width");

        in_stream_ >> tile_height;
        INTERPRETER_SYNTEX_CHECK(',', "comma", "tile height");

        in_stream_ >> stride;
        INTERPRETER_SYNTEX_CHECK(',', "comma", "stride");

        in_stream_ >> elem_width;

        INTERPRETER_SYNTEX_CHECK(')', "closing parenthesis",
                                 "source parameters");

        INTERPRETER_SYNTEX_CHECK(',', "comma", "source parameters pack");

        std::string reg_name;
        in_stream_ >> reg_name;

        if (reg_name == "%ra") {
            dst_reg = 0;
        } else if (reg_name == "%rb") {
            dst_reg = 1;
        } else if (reg_name == "%rc") {
            dst_reg = 2;
        } else {
            std::cerr << "invalid register in line: " << line_ << std::endl;
            exit(1);
        }

        INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

        for (int row = 0; row < tile_height; ++row) {
            for (int col = 0; col < tile_width; ++col) {
                long target = base_addr + (row * stride + col) * elem_width;

                cache_sim_.process_request('r', target);
            }
        }
    }

    // tmov <Dest Addr> <Width> <Height> <Stride> <Element Size> <reg>
    void handleTmove()
    {
        size_t base_addr;
        int tile_width;
        int tile_height;
        int stride;
        int elem_width;
        int dst_reg;

        INTERPRETER_SYNTEX_CHECK('(', "opening parenthesis", "command name");

        in_stream_ >> std::hex >> base_addr;
        INTERPRETER_SYNTEX_CHECK(',', "comma", "base address");

        in_stream_ >> std::dec >> tile_width;
        INTERPRETER_SYNTEX_CHECK(',', "comma", "tile width");

        in_stream_ >> tile_height;
        INTERPRETER_SYNTEX_CHECK(',', "comma", "tile height");

        in_stream_ >> stride;
        INTERPRETER_SYNTEX_CHECK(',', "comma", "stride");

        in_stream_ >> elem_width;

        INTERPRETER_SYNTEX_CHECK(')', "closing parenthesis",
                                 "source parameters");

        INTERPRETER_SYNTEX_CHECK(',', "comma", "source parameters pack");

        std::string reg_name;
        in_stream_ >> reg_name;

        if (reg_name == "%ra") {
            dst_reg = 0;
        } else if (reg_name == "%rb") {
            dst_reg = 1;
        } else if (reg_name == "%rc") {
            dst_reg = 2;
        } else {
            std::cerr << "invalid register in line: " << line_ << std::endl;
            exit(1);
        }
        INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");
    }

    // tmulac <SrcTile1 ID> <SrcTile2 ID> <DestTile ID>
    void handleMulAcc()
    {
        int tile_1;
        int tile_2;
        int tile_3;

        std::string reg_name;
        in_stream_ >> reg_name;

        if (reg_name == "%ra") {
            tile_1 = 0;
        } else if (reg_name == "%rb") {
            tile_1 = 1;
        } else if (reg_name == "%rc") {
            tile_1 = 2;
        } else {
            std::cerr << "invalid register in line: " << line_ << std::endl;
            exit(1);
        }
        INTERPRETER_SYNTEX_CHECK(',', "comma", "tile one");

        in_stream_ >> reg_name;

        if (reg_name == "%ra") {
            tile_2 = 0;
        } else if (reg_name == "%rb") {
            tile_2 = 1;
        } else if (reg_name == "%rc") {
            tile_2 = 2;
        } else {
            std::cerr << "invalid register in line: " << line_ << std::endl;
            exit(1);
        }

        INTERPRETER_SYNTEX_CHECK(',', "comma", "tile two");

        in_stream_ >> reg_name;

        if (reg_name == "%ra") {
            tile_3 = 0;
        } else if (reg_name == "%rb") {
            tile_3 = 1;
        } else if (reg_name == "%rc") {
            tile_3 = 2;
        } else {
            std::cerr << "invalid register in line: " << line_ << std::endl;
            exit(1);
        }
        INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");
    }

    void handleCmd()
    {
        cmd cur_cmd = readCmd();

        switch (cur_cmd) {
        case load_tile:
            handleTload();
            break;
        case move_tile:
            handleTmove();
            break;
        case mul_acc:
            handleMulAcc();
            break;
        case eof:
            return;
            break;
        }

        ++line_;
    }

    cmd readCmd()
    {
        trim_prefix_spaces();

        std::string cmd;
        std::getline(in_stream_, cmd, ' ');

        if (cmd == "ltea") {
            return load_tile;
        } else if (cmd == "tmulac") {
            return mul_acc;
        } else if (cmd == "tmov") {
            return move_tile;
        } else if (in_stream_.eof()) {
            return eof;
        } else {
            std::cerr << "invalid command" << std::endl;
            exit(1);
        }
    }

    void trim_prefix_spaces()
    {
        while (in_stream_.peek() == ' ') {
            in_stream_.ignore();
        }
    }
};

int main()
{
    simulator& sim = simulator::getInstance(6, 180, 15, 4, 2, 18, 24, 4, true);

    Interpeter inter("./matmul.matv", sim);

    std::cout << "Starting trace interpretation loop..." << std::endl;
    inter.run();

    std::cout <<                                                           //
        "Interpretation complete! Extracting cache performance records..." //
              << std::endl;

    printf("--- Workload Statistics ---\n");
    printf("L1 Miss Rate: %.03f\n", sim.calc_L1_miss_rate());
    printf("L2 Miss Rate: %.03f\n", sim.calc_L2_miss_rate());
    printf("Average Memory Access Time: %.03f cycles\n",
           sim.calc_avg_access_time());

    return 0;
};
