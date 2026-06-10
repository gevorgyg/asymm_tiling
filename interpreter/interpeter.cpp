#include "interpeter.h"

#include <cstdlib>
#include <iostream>
#include <string>

using std::filesystem::path;

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

Interpeter::Interpeter(path input_file, MemoryHierarchy& mem,
                       const std::string& trace_file_path, size_t& cpu_cycles)
    : in_stream_(input_file), line_(0), total_cycles_(cpu_cycles), mem_(mem)
{
    if (!in_stream_.is_open()) {
        std::cerr << "error opening trace file" << std::endl;
        exit(1);
    }
    if (!trace_file_path.empty()) {
        trace_out_.open(trace_file_path, std::ios::trunc);
        if (!trace_out_.is_open()) {
            std::cerr << "error opening --trace_file: " << trace_file_path
                      << std::endl;
            exit(1);
        }
    }
}

void Interpeter::doRead(Addr addr)
{
    Trace t = mem_.read(addr, 1);
    total_cycles_ += totalCycles(t);
    logTrace(t);
}

void Interpeter::doWrite(Addr addr)
{
    Trace t = mem_.write(addr, 1);
    total_cycles_ += totalCycles(t);
    logTrace(t);
}

void Interpeter::logTrace(const Trace& t)
{
    if (!trace_out_.is_open())
        return;
    for (const auto& a : t) {
        a->print(trace_out_);
        trace_out_ << '\n';
    }
}

void Interpeter::run()
{
    while (!in_stream_.eof()) {
        handleCmd();
    }
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

    if (mem_.getMagicAddr() != 0 && base_addr >= mem_.getMagicAddr()) {
        Trace t = mem_.reseedPrng(base_addr);
        total_cycles_ += totalCycles(t);
        logTrace(t);
        return;
    }

    for (int row = 0; row < tile_height; ++row) {
        for (int col = 0; col < tile_width; ++col) {
            long target = base_addr + (row * stride + col) * elem_width;

            doRead(target);
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

            doWrite(target);
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

    for (int a_row = 0; a_row < ra.t_height; ++a_row) {
        for (int b_col = 0; b_col < rb.t_width; ++b_col) {
            Addr target_c =
                rc.base_addr + (a_row * rc.stride + b_col) * rc.elem_width;

            for (int t = 0; t < ra.t_width; ++t) {
                Addr target_b =
                    rb.base_addr + (t * rb.stride + b_col) * rb.elem_width;
                doRead(target_b);

                Addr target_a =
                    ra.base_addr + (a_row * ra.stride + t) * ra.elem_width;
                doRead(target_a);
                // multiply A and B
            }

            doRead(target_c);
            doWrite(target_c);
            // accumulate in C
        }
    }
}

void Interpeter::startRng()
{
    Addr magic_addr;
    Addr seed_discard;
    in_stream_ >> std::hex >> magic_addr >> seed_discard;

    if (magic_addr == 0) {
        std::cerr << "invalid MMIO magic address in line: " << line_
                  << std::endl;
        exit(1);
    }

    mem_.startPrng(magic_addr);

    INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");
}

void Interpeter::stopRng()
{
    mem_.stopPrng();

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
