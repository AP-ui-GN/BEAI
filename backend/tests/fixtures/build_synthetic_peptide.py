"""Write the hand-built synthetic peptide used by the geometry tests.

The coordinates are chosen so the C-alpha distances and the radius of gyration
can be checked by arithmetic. This is not a biological structure.
"""

from pathlib import Path


def atom_name(name: str) -> str:
    if len(name) >= 4:
        return name[:4]
    return f" {name:<3}"


def atom_line(
    serial: int,
    name: str,
    altloc: str,
    resname: str,
    chain: str,
    resseq: int,
    x: float,
    y: float,
    z: float,
    occupancy: float,
    bfactor: float,
    element: str,
    *,
    hetatm: bool = False,
) -> str:
    record = "HETATM" if hetatm else "ATOM  "
    alt = altloc if altloc else " "
    return (
        f"{record}{serial:5d} {atom_name(name)}{alt}{resname:>3} {chain}"
        f"{resseq:4d}    {x:8.3f}{y:8.3f}{z:8.3f}{occupancy:6.2f}{bfactor:6.2f}"
        f"          {element:>2}"
    )


def build() -> str:
    lines = [
        "HEADER    SYNTHETIC                               01-JAN-00   SYN1",
        "TITLE     BEAI SYNTHETIC PEPTIDE",
        "REMARK 465",
        "REMARK 465 MISSING RESIDUES",
        "REMARK 465 THE FOLLOWING RESIDUES WERE NOT LOCATED IN THE",
        "REMARK 465 EXPERIMENT. (M=MODEL NUMBER; RES=RESIDUE NAME; C=CHAIN",
        "REMARK 465 IDENTIFIER; SSSEQ=SEQUENCE NUMBER; I=INSERTION CODE.)",
        "REMARK 465",
        "REMARK 465   M RES C SSSEQI",
        "REMARK 465     GLY A     3",
        "SEQRES   1 A    4  ALA ALA GLY ALA",
        atom_line(1, "N", "", "ALA", "A", 1, 0, 1, 0, 1, 10, "N"),
        atom_line(2, "CA", "", "ALA", "A", 1, 0, 0, 0, 1, 10, "C"),
        atom_line(3, "C", "", "ALA", "A", 1, 1, 0, 0, 1, 10, "C"),
        atom_line(4, "O", "", "ALA", "A", 1, 1, 1, 0, 1, 10, "O"),
        atom_line(5, "CB", "A", "ALA", "A", 1, 0, 0, 1, 0.70, 10, "C"),
        atom_line(6, "CB", "B", "ALA", "A", 1, 0, 0, 2, 0.30, 10, "C"),
        atom_line(7, "N", "", "ALA", "A", 2, 3, 1, 0, 1, 20, "N"),
        atom_line(8, "CA", "", "ALA", "A", 2, 3, 0, 0, 1, 20, "C"),
        atom_line(9, "C", "", "ALA", "A", 2, 4, 0, 0, 1, 20, "C"),
        atom_line(10, "O", "", "ALA", "A", 2, 4, 1, 0, 1, 20, "O"),
        atom_line(11, "N", "", "ALA", "A", 4, 8, 1, 0, 1, 30, "N"),
        atom_line(12, "CA", "", "ALA", "A", 4, 8, 0, 0, 1, 30, "C"),
        atom_line(13, "C", "", "ALA", "A", 4, 9, 0, 0, 1, 30, "C"),
        atom_line(14, "O", "", "ALA", "A", 4, 9, 1, 0, 1, 30, "O"),
        atom_line(15, "CB", "", "ALA", "A", 4, 8, 0, 1, 1, 30, "C"),
        atom_line(16, "O", "", "HOH", "A", 101, 20, 20, 20, 1, 40, "O", hetatm=True),
        "END",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    destination = Path(__file__).with_name("synthetic_peptide.pdb")
    destination.write_text(build(), encoding="ascii")


if __name__ == "__main__":
    main()
