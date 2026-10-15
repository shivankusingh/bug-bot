// Code your testbench here
module tb();

  reg clk;
  reg reset;
  reg [2:0] spikes_in;
  wire signed [15:0] voltage;
  wire spike;
  integer i;
  reg signed [15:0] expected_v [0:15];
  reg expected_spike [0:15];
  reg [2:0] input_table [0:15];

  lif_neuron test_bench_copy (
    .clk(clk),
    .reset(reset),
    .spikes_in(spikes_in),
    .voltage(voltage),
    .spike(spike)
  );

  // clock: starts at 0, flips every 5 → one rising edge every 10
  initial begin
    clk = 0;
  end

  always begin
    #5;
    clk = !clk;
  end

  // the test
  initial begin
    $readmemh("newSpikesInSaved.txt", input_table);
	$readmemh("expected_v.txt", expected_v);
	$readmemh("expected_spike.txt", expected_spike);
    // reset
    reset = 1;
    spikes_in = 0;
    @(posedge clk); #1; reset = 0;

    // feed one input per tick and print the result
    for (i = 0; i < 16; i = i + 1) begin
      spikes_in = input_table[i];        // put this step's input on the wire
      @(posedge clk);             // neuron takes one step
      #1;                         // let the outputs update
      $display("step %3d  input %b  v %5d  spike %0d", i, spikes_in, voltage, spike);
      if (voltage !== expected_v[i] || spike !== expected_spike[i]) begin
  $display("MISMATCH at step %0d: expected v=%0d spike=%0d, got v=%0d spike=%0d",
           i, expected_v[i], expected_spike[i], voltage, spike);
  $finish;
end
    end
$display("PASS: all 16 steps match");
    $finish;
  end

endmodule
