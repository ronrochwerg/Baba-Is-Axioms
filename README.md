# Baba Is Axioms

This repository contains the PDDL domain, benchmark problems, level images, and
planner outputs accompanying a paper submitted to the **ICAPS RPG Workshop
2026**. The domain models *Baba Is You* as a fully observable deterministic
planning problem with an emphasis on derived predicates.

## Repository contents

- `domain.pddl`: the Baba Is You planning domain.
- `problem_files/`: benchmark problem instances and level metadata.
- `problem_outputs/`: planner logs and plans, grouped by search configuration.
- `level_images/`: reference images for the benchmark levels.
- `problem_gen.py`: a graphical editor for creating PDDL problem instances.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) for running the PDDL problems.
- Python 3 with Tkinter for using the problem generator. Tkinter is included in
  standard Python installations on Windows and macOS. On Debian or Ubuntu, it
  can be installed with `sudo apt install python3-tk`.

## Running the PDDL problems with Docker

The commands below use the Planutils image, which provides Fast Downward and
other planning tools.

From the repository root, create and enter a container.

PowerShell:

```powershell
docker run -it --name baba-is-axioms -v "${PWD}:/root/baba-is-axioms" --privileged aiplanning/planutils:latest bash
```

Command Prompt:

```cmd
docker run -it --name baba-is-axioms -v "%cd%:/root/baba-is-axioms" --privileged aiplanning/planutils:latest bash
```

Inside the container, activate Planutils and run a benchmark problem with Fast
Downward:

```bash
cd /root/baba-is-axioms
planutils activate
downward domain.pddl problem_files/small_01.pddl --search "astar(blind())"
```

Fast Downward writes the plan to `sas_plan` by default. To leave the container,
run `exit`. To use the same container again later:

```bash
docker start -ai baba-is-axioms
```

Different Fast Downward search configurations can be supplied through the
`--search` argument. The directories under `problem_outputs/` contain the logs
and plans produced by the configurations used for the accompanying experiments.

## Creating a problem with `problem_gen.py`

The generator is a Tkinter desktop application and should be run on the host,
not inside the Docker container. Start a new editor with explicit grid
dimensions:

```bash
python problem_gen.py --width 6 --height 4 --name my_level
```

The default output is `problem_files/<name>.pddl`. An explicit output path and
domain name can also be supplied:

```bash
python problem_gen.py --width 6 --height 4 --name my_level --domain baba --output problem_files/my_level.pddl
```

If `--width` or `--height` is omitted, the generator prompts for it in the
terminal. In the editor, select a sprite, text block, or erase tool and click a
grid cell to modify it. Use **Write PDDL** to export the problem. Layouts can
also be saved as JSON from the editor and loaded later:

```bash
python problem_gen.py --load-layout path/to/layout.json --name my_level --output problem_files/my_level.pddl
```

When loading JSON, the saved layout determines the grid dimensions. Run
`python problem_gen.py --help` for the complete command-line reference.

## Citation

Citation information will be added when the workshop paper is available.
