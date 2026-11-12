# Level snapshots (`*.levels.npz`) and the `snapshots` branch

Runs with `run.save_params=true` (paired displacement: P4, A3*/P8, H5, B5 and their clean twins) also write
the parameter trajectory of every level, one float16 snapshot per block. These files are large (37-375 MB
each; GitHub accepts at most 100 MB per file), `*.npz` is in `.gitignore`, and they are not on `main`.

They are kept on the branch **`snapshots`** of this repository, an archive branch that shares no history
with `main`. Files above 90 MB are cut into parts there; a manifest per machine lists every file with its
size, its sha256 and its parts. The same branch holds the pretrained-weight caches (`cache/pretrain/*.pt`)
of the machines and the few other files a machine held that are not on `main` (figures and tables it drew
from its own snapshots).

Nothing in the paper needs them: `scripts/paired_disp.py` stores everything it derives from a snapshot (the
paired displacement of every level, of the anchor and the movement of each run, fields `paired_disp`,
`paired_anchor`, `paired_move`, `paired_with`) in the attacked run's JSON record, and the tables and
figures are computed from those fields. A snapshot is also deterministic given the record's configuration
and seed: re-running that configuration (`scripts/run_experiment.py ... --set run.save_params=true`) on the
same kind of machine writes it again.

## Getting the files

    python scripts/restore_snapshots.py                  # every level snapshot, next to its JSON record
    python scripts/restore_snapshots.py --list           # what is on the branch
    python scripts/restore_snapshots.py --machine pool1  # the snapshots of one machine
    python scripts/restore_snapshots.py --only pretrain_cache --machine cloud   # a machine's pretrained weights
    python scripts/restore_snapshots.py --only machine_file                     # the other files, into results_archive/<machine>/

The script downloads only the parts it needs (into a temporary folder next to the clone, about twice the
size of what is restored), joins them and checks the sha256 of every file before it puts it in place. A
different file already in that place is kept beside it as `<name>.local`. With the snapshots in place, `make paper` recomputes the stored displacements from them
and the records, tables and figures come out unchanged (checked on a fresh clone for P4, seeds 10-14 from
three machines, for the drift-guard runs H5 and for the long drift runs B5, seeds 10-11 from two machines;
only the creation date inside the PDF figures differs).

## Cloning without the archive

    git clone --single-branch --branch main https://github.com/abraheemrashid99-sys/Citradel-Rx

A plain `git clone`, and a plain `git fetch` or `git pull` in an older clone, also download the `snapshots`
branch. `git pull origin main` fetches `main` only.

## Adding the files of another machine

    python scripts/archive_machine_snapshots.py --machine windows --dry   # list
    python scripts/archive_machine_snapshots.py --machine windows         # store

stores everything the clone on that machine holds that is not on GitHub (untracked, ignored or modified
files: level snapshots, the pretrain cache, figures, logs) under `machines/<machine>/` on the branch, with
`manifests/<machine>.json`. It does not change the clone and does not download what is already archived.
Run again later, it adds what is new and keeps the earlier entries; content that changed since it was
stored is refused unless `--replace` is given.

## What is on the branch

Every level snapshot of the revision is there (24 files). The machines that are not listed (pool3,
pool6-pool11 and the helper machine) held no snapshot and no file missing from `main`, only their
pretrain caches, which were not archived: the first run of a configuration writes its cache again.

<!-- tables from the manifests on the snapshots branch at e6920801cf5c -->
| machine | level snapshots | MB | pretrain caches | MB | other files | MB |
|---|---|---|---|---|---|---|
| cloud | 14 | 1249 | 54 | 98 | 0 | 0.0 |
| pool1 | 3 | 107 | 16 | 35 | 5 | 0.2 |
| pool2 | 3 | 107 | 15 | 31 | 5 | 0.2 |
| pool4 | 2 | 714 | 27 | 42 | 3 | 0.1 |
| pool5 | 2 | 714 | 27 | 42 | 3 | 0.1 |
| **all** | **24** | **2891** | **139** | **248** | **16** | **0.7** |

| machine | file | MB | sha256 |
|---|---|---|---|
| cloud | `results/rev2_drift_guard/h5_a3star_e0.05_guard__long_s10_228773785711.levels.npz` | 143 | `5bc3135f2049b8235b7bc9a07e1e35ac14e0b2b84b2b397b4b7b520514158750` |
| cloud | `results/rev2_drift_guard/h5_a3star_e0.05_guard__long_s11_9e49237c4cf0.levels.npz` | 143 | `c9c7c1fe753fdc87fccca54825148af578a11901ef155029c926d5e5c5a57577` |
| cloud | `results/rev_clean_cloud/clean_265be639e5_s10_e8d895ab47e0.levels.npz` | 143 | `37b45e5584b14ee264b4bc300e11a4aa67692f6b410b053cc0e638bbd1c9485b` |
| cloud | `results/rev_clean_cloud/clean_265be639e5_s11_832eeef7a101.levels.npz` | 143 | `e9ccc5e023121c0d6b4513ee6f50e2478bdca10cd333cec7863038de0128ae65` |
| cloud | `results/rev_clean_cloud/clean_3b3e8e4941_s10_964cda537d56.levels.npz` | 36 | `efedf0007674410eaebe2617826b3fc7bc229fe3391826c4affb08dae59a900e` |
| cloud | `results/rev_clean_cloud/clean_3b3e8e4941_s11_d9a0ef005fd2.levels.npz` | 36 | `fe1e407329168965fc5d5162ec908fb13bc474e5aced7500104c1964eea236f8` |
| cloud | `results/rev_clean_cloud/clean_3b3e8e4941_s12_98d1f8348318.levels.npz` | 36 | `c0a01dd50394e7e6f7c695fe7e9c751c4128b2a8d0773296afa91b647a1f7fca` |
| cloud | `results/rev_clean_cloud/clean_a14ebcbf4c_s11_0af73751a678.levels.npz` | 357 | `b7a4ff6a8ad4e7e0c0db2051a61a7188f19531973240c886fafc6b56b32451c5` |
| cloud | `results/rev_p4_paired/p4_citadel__sir0_s10_73b2823d82c9.levels.npz` | 36 | `8341917c83db801e532eb548ccb27aed6e59a63a2671b1ea90c95a5ffda1fb29` |
| cloud | `results/rev_p4_paired/p4_citadel__sir0_s11_19e14c40eb21.levels.npz` | 36 | `8dd5f28417e617d5615d4c7ce75c4877c21dffb923acf4d4ba4b268d8231dc7c` |
| cloud | `results/rev_p4_paired/p4_citadel__sir0_s12_4f46f97a6a83.levels.npz` | 36 | `8a963608c428751de7ef0ef734ae48e73a8235b3bf251a7611725d7922fcaa25` |
| cloud | `results/rev_p4_paired/p4_citadel__sir10_s10_5f0413fbf2f4.levels.npz` | 36 | `5ea8eaa0186033ad203e80e1dea3489752f01c386d8210afa06ea40b73e08323` |
| cloud | `results/rev_p4_paired/p4_citadel__sir10_s11_794929b771cd.levels.npz` | 36 | `9007f9125c5ea3c06528bc0c75e3e782a2fd90a13eccd5d3c753cf595dabe432` |
| cloud | `results/rev_p4_paired/p4_citadel__sir10_s12_bab27f7112d4.levels.npz` | 36 | `f233e27b25c4e3b326fdd74f85b0cc4d716e8bd33692280c66a7980ad113845f` |
| pool1 | `results/rev_clean_pool1/clean_3b3e8e4941_s13_6c968b712d10.levels.npz` | 36 | `2cac0cfcffc5af082b78e1e83b4572f876001bd92515d8fd32b9360780ecfc63` |
| pool1 | `results/rev_p4_paired/p4_citadel__sir0_s13_54eb130aaa0e.levels.npz` | 36 | `697aa9803dd3f95414b257d3315fc1a41bf8020b9d893e8fba10ccc69fad2885` |
| pool1 | `results/rev_p4_paired/p4_citadel__sir10_s13_52e38583ead9.levels.npz` | 36 | `487a7fc29410ec3373f8a816cdca4e9744944fcf4c9f32a599ba5dbeb3a48d25` |
| pool2 | `results/rev_clean_pool2/clean_3b3e8e4941_s14_14920dfb07cb.levels.npz` | 36 | `6dfe85b9281b073837cb614c8d1e3878a09d103d3916194dc0d4a774c8d19a91` |
| pool2 | `results/rev_p4_paired/p4_citadel__sir0_s14_ef13c0b5a1f7.levels.npz` | 36 | `7eea94997c422fa053fb708a00f5e845084460e3b3c83d940fcfc46c9092adec` |
| pool2 | `results/rev_p4_paired/p4_citadel__sir10_s14_2d7c3fd28fbe.levels.npz` | 36 | `edde1052e60dafe2a8d9882d5d97228afb78752949f360972c2a3ea3da29a2b2` |
| pool4 | `results/rev2_drift_long/b5_a3star_e0.05__long1000_s10_3a5da08a3aa0.levels.npz` | 357 | `06c76eb25d039f21378d487a7066d1a7cf725bb6bc3eecb40e685712cfe31941` |
| pool4 | `results/rev_clean_pool4/clean_a14ebcbf4c_s10_59377215eaa6.levels.npz` | 357 | `4ec39eea2ed3c296acf6d50715be395b32ff4d57cc7dd74969484562e18dbf04` |
| pool5 | `results/rev2_drift_long/b5_a3star_e0.05__long1000_s11_283ff7dccd8d.levels.npz` | 357 | `03285e7238217b27958af4f9cbb90058c9c9dc7ceb94f7f6f419ac8c2e51946d` |
| pool5 | `results/rev_clean_pool5/clean_a14ebcbf4c_s11_28a68942c633.levels.npz` | 357 | `b7a4ff6a8ad4e7e0c0db2051a61a7188f19531973240c886fafc6b56b32451c5` |

| machine | file kept under `results_archive/<machine>/` | bytes |
|---|---|---|
| pool1 | `docs/PAIRED_DISP_rev_p4_paired.md` | 335 |
| pool1 | `docs/figures/pool1_paired_rev_p4_paired_a1_sir0_clip.pdf` | 19456 |
| pool1 | `docs/figures/pool1_paired_rev_p4_paired_a1_sir0_clip.png` | 84092 |
| pool1 | `docs/figures/pool1_paired_rev_p4_paired_a1_sir10_clip.pdf` | 19463 |
| pool1 | `docs/figures/pool1_paired_rev_p4_paired_a1_sir10_clip.png` | 85020 |
| pool2 | `docs/PAIRED_DISP_rev_p4_paired.md` | 335 |
| pool2 | `docs/figures/pool2_paired_rev_p4_paired_a1_sir0_clip.pdf` | 19446 |
| pool2 | `docs/figures/pool2_paired_rev_p4_paired_a1_sir0_clip.png` | 82803 |
| pool2 | `docs/figures/pool2_paired_rev_p4_paired_a1_sir10_clip.pdf` | 19455 |
| pool2 | `docs/figures/pool2_paired_rev_p4_paired_a1_sir10_clip.png` | 84434 |
| pool4 | `docs/PAIRED_DISP_rev2_drift_long.md` | 290 |
| pool4 | `docs/figures/pool4_paired_rev2_drift_long_a3star_sir0_e0.05_clip.pdf` | 55611 |
| pool4 | `docs/figures/pool4_paired_rev2_drift_long_a3star_sir0_e0.05_clip.png` | 81222 |
| pool5 | `docs/PAIRED_DISP_rev2_drift_long.md` | 290 |
| pool5 | `docs/figures/pool5_paired_rev2_drift_long_a3star_sir0_e0.05_clip.pdf` | 55702 |
| pool5 | `docs/figures/pool5_paired_rev2_drift_long_a3star_sir0_e0.05_clip.png` | 80833 |
