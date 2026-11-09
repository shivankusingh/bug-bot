// board: the Basys 3 itself. Turns the board's 100 MHz clock into 50 MHz and runs top on it.
// Vivado only: clk_wiz_0 is made by Vivado's Clocking Wizard, which Icarus doesn't have,
// so the simulation tests use top.v directly.
module board #(
    parameter MEM_DIR = "../data/mem/full"  // Vivado needs the absolute path (set as a generic)
)(
    input clk,                              // 100 MHz, pin W5
    input btnC,
    input btnU,
    input btnD,
    output [15:0] led
);

    wire clk50;                             // 50 MHz, made from clk
    wire locked;                            // 1 once clk50 is steady

    clk_wiz_0 clock_maker (
        .clk_in1(clk),
        .reset(1'b0),
        .clk_out1(clk50),
        .locked(locked)
    );

    // Hold everything in reset until the 50 MHz clock is steady (or while btnC is held).
    top #(.MEM_DIR(MEM_DIR)) bug_bot (
        .clk(clk50),
        .btnC(btnC | ~locked),
        .btnU(btnU),
        .btnD(btnD),
        .led(led)
    );

endmodule
