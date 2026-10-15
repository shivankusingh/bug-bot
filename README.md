# bug-bot

Putting a real animal's brain on a chip: the *C. elegans* worm's 302-neuron connectome,
implemented as a spiking neural network on an FPGA and driving a small robot.

**Status:** in progress (foundations phase)

## How it works
- Each neuron is an integer **leaky integrate-and-fire (LIF)** model: voltage leaks each tick
  (`v - (v >> 3)`), adds weighted input spikes, fires at a threshold of 256, then resets.
- Neurons are connected by excitatory (positive) and inhibitory (negative) weighted synapses,
  with a one-tick synaptic delay.
- Every design is built first as a **Python reference model**, then in **Verilog**, and checked
  bit-for-bit with a self-checking testbench.

## Progress
- [x] Single LIF neuron in Python and Verilog, outputs match exactly
- [x] 3-input neuron with an inhibitory input (signed arithmetic in Verilog), verified bit-exact
- [x] 4-neuron network in Python: excitatory chain A → B → C plus an inhibitory interneuron
- [ ] 4-neuron network in Verilog
- [ ] Run on real FPGA hardware (Vivado)
- [ ] Load real C. elegans wiring (touch-withdrawal circuit first)
- [ ] Full 302-neuron brain in hardware
- [ ] Sensors + motors: robot reacts to touch

## Files
- `bug_bot.ipynb`: Python reference models
- `lif_neuron.v`: Verilog LIF neuron
- `tb_lif_neuron.v`: self-checking testbench
- `log.md`: day-by-day development log
