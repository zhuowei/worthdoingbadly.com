#include <idc.idc>
static main() {
    // inspired by https://github.com/gdbinit/idc-scripts/blob/master/create_and_label_sysent_entries.idc
    auto location, addr;
    location = get_name_ea_simple("__CFAppVersionCheckLessThan");
    for (addr = get_first_cref_to(location); addr != BADADDR; addr = get_next_cref_to(location, addr)) {
        auto cmp_addr = addr;
        auto functionname = get_func_name(addr);
        auto funcstart = get_func_attr(addr, FUNCATTR_START);
        auto firstXrefToSelf = get_first_cref_to(funcstart);
        if (firstXrefToSelf == BADADDR) {
            firstXrefToSelf = get_first_dref_to(funcstart);
        }
        auto firstXref = "";
        if (firstXrefToSelf != BADADDR) {
            firstXref = get_func_name(firstXrefToSelf);
        }
        auto i;
        // search backwards for first move to esi
        for (i = 0; i < 5; i++) {
            cmp_addr = find_code(cmp_addr, SEARCH_UP);
            if (print_insn_mnem(cmp_addr) == "lea") {
                // grab the comment, which has the bundle ID
                jumpto(cmp_addr);
                auto bundleid = get_curline();
                msg("%s!!!!%s!!!!%s\n", functionname, firstXref, bundleid);
                break;
            }
        }
    }
}