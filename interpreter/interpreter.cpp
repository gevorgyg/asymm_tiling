#include "interpreter.h"
#include "matmul/matmul_actions.h"

#include <cstdlib>
#include <iostream>
#include <string>

using std::filesystem::path;


Interpreter::Interpreter(path input_file, MemoryHierarchy& mem, Options opts,
                         size_t& cpu_cycles)
    : in_stream_(input_file), line_(0), cpu_cycles_(cpu_cycles),
      trace_level_(opts.trace_level), vec_regs_{}, mem_(mem),
      reg_m_(opts.reg_m), reg_n_(opts.reg_n), reg_k_(opts.reg_k),
      mulac_cycles_(opts.mulac_cycles)
{
    if (!in_stream_.is_open()) {
        std::cerr << "error opening trace file" << std::endl;
        exit(1);
    }
    if (!opts.trace_file_path.empty()) {
        trace_out_.open(opts.trace_file_path, std::ios::trunc);
        if (!trace_out_.is_open()) {
            std::cerr << "error opening --trace_file: " << opts.trace_file_path
                      << std::endl;
            exit(1);
        }
    }
}

void Interpreter::run()
{
    while (handleCmd()) { }
}


// --- Dispatch ---------------------------------------------------------------

bool Interpreter::handleCmd()
{
    // Op-table dispatch: textual op name -> handler. Order is unimportant
    // (linear scan); the table is the one place a new op registers itself.
    struct OpEntry {
        const char* name;
        void (Interpreter::*handler)();
    };
    static constexpr OpEntry kOps[] = {
        {"ltea",     &Interpreter::handleTload},
        {"tmov",     &Interpreter::handleTmove},
        {"prefetch", &Interpreter::handlePrefetch},
        {"tmulac",   &Interpreter::handleMulAcc},
    };

    skipSpaces();

    std::string op;
    std::getline(in_stream_, op, ' ');
    if (in_stream_.eof()) return false;

    for (const auto& entry : kOps) {
        if (op == entry.name) {
            inst_header_.clear();
            inst_detail_.str("");
            inst_trace_.clear();
            const size_t cycles_before = cpu_cycles_;

            (this->*entry.handler)();

            // Drain any non-access Actions the handler parked in inst_trace_
            // (only handleMulAcc uses this today). doRead/doWrite have
            // already emitted their per-access detail into inst_detail_.
            if (trace_out_.is_open() && trace_level_ >= trace_actions) {
                for (const auto& a : inst_trace_) {
                    inst_detail_ << "    ";
                    a->print(inst_detail_);
                    inst_detail_ << '\n';
                }
            }

            if (trace_out_.is_open()) {
                trace_out_ << inst_header_ << "    # "
                           << (cpu_cycles_ - cycles_before) << " cy\n"
                           << inst_detail_.str();
            }
            ++line_;
            return true;
        }
    }

    std::cerr << "invalid command '" << op << "' on line " << line_ << std::endl;
    exit(1);
}


// --- Per-op handlers --------------------------------------------------------

void Interpreter::handleTload()
{
    const TileParams p = parseTileParams();
    expect(',', "comma", "source parameters pack");
    const uint dst_reg = parseReg();
    expect('\n', "new line", "line");

    validateRegShape(dst_reg, p.t_width, p.t_height);
    vec_regs_[dst_reg] = {p.base_addr, p.t_width, p.t_height, p.stride, p.elem_width};
    setInstHeader("ltea", p, static_cast<int>(dst_reg));

    // Generated tiles must consist of whole cache lines; partial-line rows
    // are deliberately unsupported for now.
    const PrngDev& prng = mem_.prng();
    if (prng.contains(p.base_addr) &&
        (p.t_width * p.elem_width) % prng.lineSize() != 0) {
        std::cerr << "PRNG tile row of " << p.t_width * p.elem_width
                  << " bytes is not a multiple of the cache line size ("
                  << prng.lineSize() << ") in line: " << line_ << std::endl;
        exit(1);
    }

    forEachElement(p, [&](Addr a) { doRead(a, p.elem_width); });
}

void Interpreter::handleTmove()
{
    const TileParams p = parseTileParams();
    expect(',', "comma", "source parameters pack");
    const uint src_reg = parseReg();
    expect('\n', "new line", "line");

    validateRegShape(src_reg, p.t_width, p.t_height);
    setInstHeader("tmov", p, static_cast<int>(src_reg));

    forEachElement(p, [&](Addr a) { doWrite(a, p.elem_width); });
}

void Interpreter::handlePrefetch()
{
    const TileParams p = parseTileParams();
    expect('\n', "new line", "line");
    setInstHeader("prefetch", p, -1);

    forEachElement(p, [&](Addr a) { doRead(a, p.elem_width); });
}

// tmulac %ra, %rb, %rc -- pure register-file compute. Tiles were brought
// into the vector registers by ltea, so there is no memory traffic unless
// register tiling is disabled (REG_M == 0), in which case the interpreter
// emulates the scalar element loads/stores explicitly.
void Interpreter::handleMulAcc()
{
    const uint a = parseReg();
    const uint b = parseReg();
    const uint c = parseReg();
    expect('\n', "new line", "line");

    const vec_reg& ra = vec_regs_[a];
    const vec_reg& rb = vec_regs_[b];
    const vec_reg& rc = vec_regs_[c];

    if (ra.t_width != rb.t_height || rc.t_height != ra.t_height ||
        rc.t_width != rb.t_width) {
        std::cerr << "tmulac tile shape mismatch (" << ra.t_height << "x"
                  << ra.t_width << ") * (" << rb.t_height << "x" << rb.t_width
                  << ") -> (" << rc.t_height << "x" << rc.t_width
                  << ") in line: " << line_ << std::endl;
        exit(1);
    }

    std::ostringstream h;
    h << "tmulac %r" << "abc"[a] << ", %r" << "abc"[b] << ", %r" << "abc"[c];
    inst_header_ = h.str();

    // Scalar fallback when no register tiling: every multiply-accumulate
    // reads operands and writes back the accumulator through the cache.
    if (reg_m_ == 0) {
        for (uint i = 0; i < rc.t_height; ++i) {
            for (uint j = 0; j < rc.t_width; ++j) {
                const Addr c_addr = rc.base_addr + (i * rc.stride + j) * rc.elem_width;
                doRead(c_addr, rc.elem_width);
                for (uint k = 0; k < ra.t_width; ++k) {
                    const Addr a_addr = ra.base_addr + (i * ra.stride + k) * ra.elem_width;
                    doRead(a_addr, ra.elem_width);
                    const Addr b_addr = rb.base_addr + (k * rb.stride + j) * rb.elem_width;
                    doRead(b_addr, rb.elem_width);
                }
                doWrite(c_addr, rc.elem_width);
            }
        }
    }

    if (mulac_cycles_ > 0) {
        inst_trace_.push_back(std::make_unique<MulAcc>(mulac_cycles_));
        cpu_cycles_ += mulac_cycles_;
    }
}


// --- Parsing helpers --------------------------------------------------------

Interpreter::TileParams Interpreter::parseTileParams()
{
    expect('(', "opening parenthesis", "command name");
    TileParams p;
    in_stream_ >> std::hex >> p.base_addr;
    expect(',', "comma", "base address");
    in_stream_ >> std::dec >> p.t_width;
    expect(',', "comma", "tile width");
    in_stream_ >> p.t_height;
    expect(',', "comma", "tile height");
    in_stream_ >> p.stride;
    expect(',', "comma", "stride");
    in_stream_ >> p.elem_width;
    expect(')', "closing parenthesis", "source parameters");
    return p;
}

uint Interpreter::parseReg()
{
    std::string reg_name;
    in_stream_ >> reg_name;
    if (!reg_name.empty() && reg_name.back() == ',') {
        reg_name.pop_back();
    }
    if (reg_name == "%ra") return 0;
    if (reg_name == "%rb") return 1;
    if (reg_name == "%rc") return 2;

    std::cerr << "invalid register in line: " << line_ << std::endl;
    exit(1);
}

void Interpreter::expect(char c, const char* missing, const char* context)
{
    int cur = in_stream_.get();
    while (cur != c) {
        if (cur != ' ') {
            std::cerr << "missing " << missing << " after " << context
                      << " in line: " << line_ << std::endl;
            exit(1);
        }
        cur = in_stream_.get();
    }
}

void Interpreter::skipSpaces()
{
    while (in_stream_.peek() == ' ') {
        in_stream_.ignore();
    }
}


// --- Cross-cutting helpers --------------------------------------------------

// Reject loads/stores whose tile shape doesn't match the configured hardware
// register tile (REG_M/REG_N/REG_K). 1x1 accesses bypass the check so scalar
// fallback paths still work. The expected (width, height) depends on which
// register (%ra/%rb/%rc) is targeted.
void Interpreter::validateRegShape(uint reg, uint t_width, uint t_height) const
{
    if (reg_m_ == 0) return;
    if (t_width == 1 && t_height == 1) return;

    uint exp_w = 0, exp_h = 0;
    const char* reg_name = "?";
    switch (reg) {
        case 0: exp_w = reg_k_; exp_h = reg_m_; reg_name = "%ra"; break;
        case 1: exp_w = reg_n_; exp_h = reg_k_; reg_name = "%rb"; break;
        case 2: exp_w = reg_n_; exp_h = reg_m_; reg_name = "%rc"; break;
    }
    if (t_width != exp_w || t_height != exp_h) {
        std::cerr << "Error: register " << reg_name << " tile dimensions ("
                  << t_width << "x" << t_height
                  << ") do not match hardware config (" << exp_w << "x"
                  << exp_h << ")\n";
        exit(1);
    }
}

void Interpreter::setInstHeader(const char* op, const TileParams& p, int reg)
{
    std::ostringstream h;
    h << op << " (0x" << std::hex << p.base_addr << std::dec << ", "
      << p.t_width << ", " << p.t_height << ", " << p.stride << ", "
      << p.elem_width << ")";
    if (reg >= 0) {
        h << ", %r" << "abc"[reg];
    }
    inst_header_ = h.str();
}


// --- Trace I/O --------------------------------------------------------------

void Interpreter::doRead(Addr addr, size_t size)
{
    Trace t;
    mem_.access(addr, size, /*is_write=*/false, t);
    const uint cycles = totalCycles(t);
    cpu_cycles_ += cycles;
    logAccess("read ", addr, cycles, t);
}

void Interpreter::doWrite(Addr addr, size_t size)
{
    Trace t;
    mem_.access(addr, size, /*is_write=*/true, t);
    const uint cycles = totalCycles(t);
    cpu_cycles_ += cycles;
    logAccess("write", addr, cycles, t);
}

void Interpreter::logAccess(const char* op, Addr addr, uint cycles,
                            const Trace& t)
{
    if (!trace_out_.is_open() || trace_level_ < trace_accesses) return;

    inst_detail_ << "  " << op << " @0x" << std::hex << addr << std::dec
                 << " (" << cycles << " cy)\n";

    if (trace_level_ < trace_actions) return;
    for (const auto& a : t) {
        inst_detail_ << "    ";
        a->print(inst_detail_);
        inst_detail_ << '\n';
    }
}
