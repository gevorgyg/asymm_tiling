#include "interpeter.h"
#include "instgen.h"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

using std::filesystem::path;

static constexpr int block_size = 6;

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

Interpeter::Interpeter(path input_file, Simulator& cache_sim, RecordBook& rb)
    : in_stream_(input_file), line_(0), cache_sim_(cache_sim), prng_dev_(rb),
      rb_(rb)
{
    if (!in_stream_.is_open()) {
        std::cerr << "error opening trace file" << std::endl;
        exit(1);
    }
}

void Interpeter::run()
{
    while (!in_stream_.eof()) {
        handleCmd();
    }
}

void Interpeter::stall(size_t amount)
{
    rb_.total_access_cycles += amount;
}

void Interpeter::handleTload()
{
    Addr base_addr;
    uint tile_width;
    uint tile_height;
    uint stride;
    uint elem_width;
    uint dst_reg;

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

    INTERPRETER_SYNTEX_CHECK(')', "closing parenthesis", "source parameters");

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

    vec_regs_[dst_reg] = {base_addr, tile_width, tile_height, stride,
                          elem_width};

    INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

    for (int row = 0; row < tile_height; ++row) {
        for (int col = 0; col < tile_width; ++col) {
            long target = base_addr + (row * stride + col) * elem_width;

            cache_sim_.process_request('r', target);
        }
    }
}

void Interpeter::handleTmove()
{
    Addr base_addr;
    uint tile_width;
    uint tile_height;
    uint stride;
    uint elem_width;
    uint dst_reg;

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

    INTERPRETER_SYNTEX_CHECK(')', "closing parenthesis", "source parameters");

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

    vec_regs_[dst_reg] = {base_addr, tile_width, tile_height, stride,
                          elem_width};

    INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

    for (int row = 0; row < tile_height; ++row) {
        for (int col = 0; col < tile_width; ++col) {
            long target = base_addr + (row * stride + col) * elem_width;

            cache_sim_.process_request('w', target);
        }
    }
}

// tmulac <SrcTile1 ID> <SrcTile2 ID> <DestTile ID>
void Interpeter::handleMulAcc()
{
    int tile_1;
    int tile_2;
    int tile_3;

    std::string reg_name;
    in_stream_ >> reg_name;
    if (reg_name.back() == ',') {
        reg_name.pop_back();
    } else {
        std::cerr << "missing ',' after first register in line: " << line_
                  << std::endl;
        exit(1);
    }

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

    in_stream_ >> reg_name;
    if (reg_name.back() == ',') {
        reg_name.pop_back();
    } else {
        std::cerr << "missing ',' after first register in line: " << line_
                  << std::endl;
        exit(1);
    }

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

    const vec_reg& ra = vec_regs_[tile_1];
    const vec_reg& rb = vec_regs_[tile_2];
    const vec_reg& rc = vec_regs_[tile_3];

    bool use_magic = rb.base_addr == magic_addr_ ? true : false;
    bool ok        = false;

    for (int a_row = 0; a_row < ra.t_height; ++a_row) {
        for (int b_col = 0; b_col < rb.t_width; ++b_col) {
            Addr target_c =
                rc.base_addr + (a_row * rc.stride + b_col) * rc.elem_width;

            for (int t = 0; t < ra.t_width; ++t) {
                Addr target_a =
                    ra.base_addr + (a_row * ra.stride + t) * ra.elem_width;
                if (use_magic) {
                    prng_dev_.pop();
                } else {
                    Addr target_b = rb.base_addr +
                                    (t * rb.stride + b_col) * rb.elem_width;
                    cache_sim_.process_request('r', target_b);
                }

                cache_sim_.process_request('r', target_a);
                // multiply A and B
            }

            cache_sim_.process_request('r', target_c);
            cache_sim_.process_request('w', target_c);
            // accumulate in C
        }
    }
}

void Interpeter::startRng()
{
    in_stream_ >> magic_addr_;

    if (magic_addr_ == 0) {
        std::cerr << "invalid MMIO magic address in line: " << line_
                  << std::endl;
        exit(1);
    }

    INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");
}

void Interpeter::stopRng()
{
    magic_addr_ = 0;

    INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");
}

void Interpeter::handleCmd()
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
    case start_rng:
        startRng();
        break;
    case stop_rng:
        stopRng();
        break;
    case eof:
        return;
        break;
    }

    ++line_;
}

Interpeter::cmd Interpeter::readCmd()
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
    } else if (cmd == "strtrng") {
        return start_rng;
    } else if (cmd == "stprng") {
        return stop_rng;
    } else if (in_stream_.eof()) {
        return eof;
    } else {
        std::cerr << "invalid command" << std::endl;
        exit(1);
    }
}

void Interpeter::trim_prefix_spaces()
{
    while (in_stream_.peek() == ' ') {
        in_stream_.ignore();
    }
}

constexpr char instruction_path[] = "./matmul.matv";

void generateInstructions(int m, int n, int k)
{
    InstGenerator gen{500, 500, 8, 500, 500, 1};

    std::ofstream ofs(instruction_path);

    if (!ofs.is_open()) {
        std::cerr << "error opening file" << std::endl;
    }

    gen.generate(m, n, k, ofs);
}

void generatePrngInstructions(int m, int n, int k)
{
    InstGenerator gen{500, 500, 8, 500, 500, 1, true};

    std::ofstream ofs(instruction_path);

    if (!ofs.is_open()) {
        std::cerr << "error opening file" << std::endl;
    }

    gen.generate(m, n, k, ofs);
}

int main(int argc, char* argv[])
{
    if (argc == 1) {
        generatePrngInstructions(4, 4, 4);

        return 0;
    }

    if (argc != 4) {
        std::cout << "There should be 3 arguments" << std::endl;
        exit(1);
    }

    int dims[3] = {std::atoi(argv[1]), std::atoi(argv[2]), std::atoi(argv[3])};

    static RecordBook rb;

    Simulator& sim =
        Simulator::getInstance(block_size, 180, 15, 4, 2, 18, 24, 2, true, rb);

    generateInstructions(dims[0], dims[1], dims[2]);

    Interpeter inter(instruction_path, sim, rb);

    std::cout << "----------------------------" << std::endl;

    std::cout << dims[0] << ' ' << dims[1] << ' ' << dims[2] << std::endl;

    std::cout << "----------------------------" << std::endl;

    inter.run();

    rb.printStats();

    return 0;
};
