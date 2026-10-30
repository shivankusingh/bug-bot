module lif_math (
    input signed [15:0] old_voltage,
    input signed [15:0] total,
    output signed [15:0] new_voltage,
    output wire spike
);

localparam signed [15:0] threshold = 16'sd256;
localparam signed [15:0] FLOOR = -16'sd512;

wire signed [15:0] temp_voltage_holder;
wire signed [15:0] voltage_after_reset; 

assign temp_voltage_holder = (old_voltage - (old_voltage >>> 3) + total);
assign spike = (temp_voltage_holder >= threshold) ? 1 : 0;

assign voltage_after_reset = (spike == 1) ? 0 : temp_voltage_holder;

assign new_voltage = (voltage_after_reset < FLOOR) ? FLOOR : voltage_after_reset;



endmodule