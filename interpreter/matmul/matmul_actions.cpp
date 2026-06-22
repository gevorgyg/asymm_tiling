#include "matmul_actions.h"

#include <ostream>


void MulAcc::print(std::ostream& os) const
{
    os << "MulAcc (" << cost_ << " cy)";
}
