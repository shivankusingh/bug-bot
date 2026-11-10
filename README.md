# bug-bot

Putting a real animal's brain on a chip: the *C. elegans* worm's 302-neuron connectome,
implemented as a spiking neural network on an FPGA and driving a small robot.

**Status:** the whole worm brain (300 neurons, 3,669 chemical synapses, 1,087 gap junctions)
**runs on a real Digilent Basys 3 FPGA board**. Press the "head" button and the worm backs up; press
"tail" and it goes forward. The LEDs show the wheel direction and speed, it never goes the wrong way,
and it goes quiet on its own afterwards. The chip design matches the Python reference model bit for
bit (every voltage and every spike) and uses about 8% of the chip. Next: the robot, with real sensors
and motors instead of buttons and LEDs, then learning on the chip.

**Live demo:** [shivankusingh.github.io/bug-bot](https://shivankusingh.github.io/bug-bot/): a 3D view of the
worm's 300 neurons. Poke the head or tail and watch the brain decide which way the robot moves, next
to a simulated Basys 3 whose LEDs and buttons play back the chip design step by step.

## How it works
- **Neurons:** each one is an integer **leaky integrate-and-fire (LIF)** model. Every tick the voltage
  leaks (`v - (v >> 3)`), adds its input, fires at a threshold of 256 and resets to 0. It never drops
  below −512, so every voltage fits easily in 16 bits.
- **Wiring:** 3,669 chemical synapses (weight = synapse count × 10, one-tick delay) and 1,087 gap
  junctions from the real connectome. Gap junctions pass voltage both ways, plus a small push when a
  neuron fires.
- **Excite or inhibit:** signs come from receptor data. Where the data can't decide, a circuit rule
  uses known biology: touch sensors block the opposite direction, and command and motor neurons on
  the same team (backward or forward) help each other while opposite teams block each other.
- **Robot readout:** backward (DA/VA) and forward (DB/VB) motor spikes fill two leaky "muscle"
  buckets; the fuller one sets the wheel direction and speed.
- **Hardware design:** one neuron circuit is reused for every neuron (time-multiplexing): a counter
  walks through memory, and the circuit updates one neuron per clock tick. The wiring lives in memory
  in a compact list format (CSR), so the same design scales from 4 neurons to the whole worm by
  loading different memory files. Each step runs five jobs in order: clear inputs, deliver touches,
  deliver last step's spikes (skipping neurons that didn't fire), gap junctions, update neurons, then
  the muscle readout decides the wheels. A worm step takes about 4,600 clock ticks, around 92 µs at
  the board's 50 MHz.
- **On the board:** the Basys 3's 100 MHz clock is turned into 50 MHz (the core's longest path needs
  a bit more than the 10 ns a 100 MHz tick allows, so 100 MHz timing isn't met yet). A step timer starts a new worm step 10 times a second,
  slow enough to watch. Buttons are touches, LEDs are the wheels.
- **Verification:** every design is built first as a **Python reference model**, then in **Verilog**,
  and checked bit-for-bit against golden files with [cocotb](https://www.cocotb.org/) testbenches
  (Icarus Verilog), one test per job plus a full replay of the 80-step touch run. The board design
  is tested the same way, through its buttons and LEDs, before it goes on the chip.

## Try it on a Basys 3
Load `logs/vivado/impl_2026-11-09_run10_board.bit` with Vivado's Hardware Manager (Open Target →
Auto Connect → right-click `xc7a35t_0` → Program Device). To rebuild it, see `verilog/board.v`.

| Button | Does |
|---|---|
| Up (`btnU`) | touch the head (hold ~1 s) |
| Down (`btnD`) | touch the tail |
| Center (`btnC`) | reset |

| LED | Shows |
|---|---|
| LD15 / LD14 | backward / forward |
| LD13 | blinks every step (the timer is running) |
| LD12 / LD11 | head / tail button seen |
| LD6–LD0 | wheel speed in binary (LD6 = 64 … LD0 = 1) |

## Progress
- [x] Single LIF neuron in Python and Verilog, outputs match exactly
- [x] 3-input neuron with an inhibitory input (signed arithmetic in Verilog), verified bit-exact
- [x] 4-neuron network in Python: excitatory chain A → B → C plus an inhibitory interneuron
- [x] 4-neuron network in Verilog, verified bit-exact
- [x] Load the real C. elegans wiring (300 neurons, chemical synapses and gap junctions)
- [x] Touch test in Python: head touch → backward, tail touch → forward, brain goes quiet afterwards
- [x] Motor neurons and robot wheel readout in Python, both directions
- [x] 16-bit safe model (voltage floor) and golden files for the full network
- [x] Live 3D demo website
- [x] Scalable Verilog core (one neuron circuit looping over all neurons, wiring in memory):
      the full 300-neuron brain matches the Python model bit-exact in simulation
- [x] Robot readout (muscle buckets) in Verilog, matches Python for the whole touch run
- [x] Fits on the FPGA: Vivado synthesis and implementation for the Basys 3 (about 8% of the chip)
- [x] Board design (buttons as touches, a step timer, LEDs as wheels), verified in simulation
- [x] Full brain on real FPGA hardware (Basys 3): head button → backward, tail button → forward,
      never the wrong way, and it goes quiet on its own afterwards
- [ ] The robot: real sensors and motors
- [ ] Learning on the chip (reward-based R-STDP, smell/light as the input)
- [ ] More senses (nose touch, then food and steering)

## Files
- `python/bug_bot.ipynb`: 4-neuron reference model (test bench for the Verilog)
- `python/touch_test.ipynb`: the full worm brain: touch test, robot readout, exports
- `python/connectome_parser.py`: builds the network from the raw data (weights, sign rules)
- `python/connectome_all.py`, `python/touch_circuit.py`: the generated networks (300 and 14 neurons)
- `python/plot_run.py`, `python/golden.py`, `python/export_web.py`: plotting, golden files, website data
- `python/make_mem.py`: turns a network into the memory files the Verilog core loads
- `verilog/core.v`: the scalable core (state machine, memories, all five jobs)
- `verilog/lif_math.v`: the neuron update as pure math, used once by the core
- `verilog/top.v`: the board design (button sync, step timer, core, LEDs), tested by `verilog/test_top.py`
- `verilog/board.v`, `verilog/board.xdc`: the Basys 3 wrapper (50 MHz clock) and its pins
- `verilog/blinky.v`, `verilog/blinky.xdc`: first board test (one blinking LED)
- `verilog/test_core_*.py`, `verilog/test_lif_math.py`: cocotb tests (one per job, plus golden-file replay)
- `verilog/lif_neuron.v`, `verilog/snn_4neuron.v`, `verilog/test_bench.v`: the first hand-wired
  4-neuron design and its testbench
- `data/`: golden files (`chain_*` for 4 neurons, `full_*` for the whole brain)
- `data/mem/`: memory files for the core (`chain/` and `full/`)
- `docs/`: the demo website (`run.json` from the Python model, `board.json` from the Verilog simulation)
- `logs/log.md`: day-by-day development log
- `logs/vivado/`: Vivado reports for every build, and the bitstream that runs on the board

## Data sources and credits
- **Wiring (who connects to whom, and how strongly):** Cook SJ, Jarrell TA, Brittin CA, et al.
  "Whole-animal connectomes of both *Caenorhabditis elegans* sexes." *Nature* 571, 63–71 (2019).
  [doi:10.1038/s41586-019-1352-7](https://doi.org/10.1038/s41586-019-1352-7).
  Hermaphrodite adjacency matrices, SI 5 (corrected July 2020).
- **Excitatory / inhibitory signs:** Fenyves BG, Szilágyi GS, Vassy Z, Sőti C, Csermely P.
  "Synaptic polarity and sign-balance prediction using gene expression data in the
  *Caenorhabditis elegans* chemical synapse neuronal connectome network."
  *PLOS Computational Biology* 16(12): e1007974 (2020).
  [doi:10.1371/journal.pcbi.1007974](https://doi.org/10.1371/journal.pcbi.1007974).
  S1 Data, used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Touch-circuit sign rule** (touch neurons inhibit the command interneurons for the opposite
  direction): Chalfie M, Sulston JE, White JG, Southgate E, Thomson JN, Brenner S.
  "The neural circuit for touch sensitivity in *Caenorhabditis elegans*."
  *Journal of Neuroscience* 5(4), 956–964 (1985).
- **Data download:** the Cook et al. spreadsheet was obtained from OpenWorm's
  [ConnectomeToolbox](https://github.com/openworm/ConnectomeToolbox) (MIT license).
