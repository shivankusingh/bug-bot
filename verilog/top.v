// top: connects the worm core to the Basys 3's buttons and LEDs.
// Everything in here runs on one clock (clk). On the board that's the 50 MHz clock made in
// board.v; in simulation the test drives clk directly (test_top.py).
//
// Buttons: btnC = reset, btnU = head poke, btnD = tail poke (hold to keep poking).
// LEDs:    led[15] = backward, led[14] = forward, led[13] = flips every step,
//          led[12] = head button seen, led[11] = tail button seen, led[6:0] = wheel speed.
module top #(
    parameter N = 300,                      // full worm (same numbers as the Vivado core project)
    parameter N_LINKS = 3744,
    parameter N_POKES = 2,
    parameter N_POKE_LINKS = 6,
    parameter N_PIPES = 1087,
    parameter MEM_DIR = "../data/mem/full",
    parameter STEP_TICKS = 5_000_000        // ticks between steps: 0.1 s at 50 MHz (10 steps/s)
)(
    input clk,
    input btnC,
    input btnU,
    input btnD,
    output [15:0] led
);

    // 1. Button sync: each button goes through two flip-flops before anything uses it.
    //    A button can change at any moment, even right on a clock edge. The first flip-flop
    //    may catch it half-changed; the second gives it a full tick to settle.
    reg [2:0] buttons_1 = 0;
    reg [2:0] buttons_2 = 0;
    always @(posedge clk) begin
        buttons_1 <= {btnC, btnU, btnD};
        buttons_2 <= buttons_1;
    end
    wire reset = buttons_2[2];
    wire head  = buttons_2[1];
    wire tail  = buttons_2[0];

    // 2. Step timer: counts 0 .. STEP_TICKS-1, then start_step is 1 for exactly one tick.
    //    23 bits holds up to 8,388,607, enough for 5,000,000.
    reg [22:0] step_count = 0;
    reg start_step = 0;
    reg heartbeat = 0;                      // flips every step, so led[13] shows the timer works
    always @(posedge clk) begin
        if (reset) begin
            step_count <= 0;
            start_step <= 0;
            heartbeat <= 0;
        end
        else if (step_count == STEP_TICKS - 1) begin
            step_count <= 0;
            start_step <= 1;                // the one tick it's 1
            heartbeat <= ~heartbeat;
        end
        else begin
            step_count <= step_count + 1;
            start_step <= 0;                // every other tick it's 0
        end
    end

    // 3. The worm.
    wire busy;
    wire [1:0] wheel_direction;
    wire [6:0] wheel_speed;
    wire [6:0] back_muscle;
    wire [6:0] forward_muscle;

    core #(
        .N(N),
        .N_LINKS(N_LINKS),
        .N_POKES(N_POKES),
        .N_POKE_LINKS(N_POKE_LINKS),
        .N_PIPES(N_PIPES),
        .MEM_DIR(MEM_DIR)
    ) worm (
        .clk(clk),
        .reset(reset),
        .start_step(start_step),
        .busy(busy),
        .pokes({tail, head}),               // bit 0 = head, bit 1 = tail (same as the tests)
        .wheel_speed(wheel_speed),
        .wheel_direction(wheel_direction),
        .back_muscle(back_muscle),
        .forward_muscle(forward_muscle)
    );

    // 4. LEDs.
    assign led[15]   = (wheel_direction == 1);  // backward
    assign led[14]   = (wheel_direction == 2);  // forward
    assign led[13]   = heartbeat;
    assign led[12]   = head;
    assign led[11]   = tail;
    assign led[10:7] = 0;
    assign led[6:0]  = wheel_speed;             // in binary: led[0] = 1, led[1] = 2, led[2] = 4, ...

endmodule
