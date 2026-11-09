// blinky: first board test for the Basys 3 (not part of the worm).
// LED 0 blinks once per second. LED 1 is on while the center button is held.
// Pins are in blinky.xdc.
module blinky #(
    parameter HALF_SECOND = 50_000_000      // ticks in 0.5 s at 100 MHz
)(
    input clk,                              // 100 MHz board clock
    input btnC,                             // center button, 1 while pressed
    output reg [1:0] led = 0                // led[0] = rightmost LED, led[1] = next one
);

    reg [25:0] count = 0;                   // 26 bits: up to 67,108,863

    always @(posedge clk) begin
        if (count == HALF_SECOND - 1) begin
            count <= 0;
            led[0] <= ~led[0];              // flip: on -> off, off -> on
        end
        else begin
            count <= count + 1;
        end
        led[1] <= btnC;
    end

endmodule
