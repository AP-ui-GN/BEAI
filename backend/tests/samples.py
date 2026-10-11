"""Tiny non-biological coordinate files for upload tests. Not scientific fixtures."""


def minimal_pdb() -> bytes:
    return (
        b"HEADER    TEST\n"
        b"TITLE     MINIMAL UPLOAD\n"
        b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 10.00           C\n"
        b"END\n"
    )


def minimal_mmcif() -> bytes:
    return b"""data_MINI
#
loop_
_struct.title
_struct.entry_id
MINIMAL_MMCIF MINI
#
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_entity_id
_atom_site.label_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.occupancy
_atom_site.B_iso_or_equiv
_atom_site.auth_seq_id
_atom_site.auth_comp_id
_atom_site.auth_asym_id
_atom_site.auth_atom_id
_atom_site.pdbx_PDB_model_num
ATOM 1 C CA . ALA A 1 1 ? 0.000 0.000 0.000 1.00 10.00 1 ALA A CA 1
#
"""


def atom_lines(count: int) -> bytes:
    lines = [b"HEADER    TEST"]
    for index in range(1, count + 1):
        atom = (
            f"ATOM  {index:5d}  CA  ALA A{index:4d}"
            "       0.000   0.000   0.000  1.00 10.00           C"
        )
        lines.append(atom.encode())
    lines.append(b"END")
    return b"\n".join(lines) + b"\n"
