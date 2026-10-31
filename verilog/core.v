module core #(
    parameter N = 4,                        // neurons
    parameter N_LINKS = 3,                  // chemical links (all senders glued together)
    parameter N_POKES = 2,                  // pokes (head, tail)
    parameter N_POKE_LINKS = 2,             // poke links (all pokes glued together)
    parameter MEM_DIR = "../data/mem/chain" // folder with the .mem files
)(
    input clk,
    input reset,
    input start_step,
    output reg busy
);

    // wiring (loaded once from MEM_DIR, never changes)
    reg [8:0]         link_receiver [0:N_LINKS-1];
    reg signed [10:0] link_weight   [0:N_LINKS-1];
    reg [11:0]        start         [0:N];
    reg [8:0]         poke_receiver [0:N_POKE_LINKS-1];
    reg signed [10:0] poke_weight   [0:N_POKE_LINKS-1];
    reg [11:0]        poke_start    [0:N_POKES];

    // brain state (one slot per neuron, changes every step)
    reg signed [15:0] voltages [0:N-1];
    reg signed [15:0] totals   [0:N-1];
    reg               spikes   [0:N-1];

    integer i;

    initial begin
        $readmemh({MEM_DIR, "/link_receiver.mem"}, link_receiver);
        $readmemh({MEM_DIR, "/link_weight.mem"},   link_weight);
        $readmemh({MEM_DIR, "/start.mem"},         start);
        $readmemh({MEM_DIR, "/poke_receiver.mem"}, poke_receiver);
        $readmemh({MEM_DIR, "/poke_weight.mem"},   poke_weight);
        $readmemh({MEM_DIR, "/poke_start.mem"},    poke_start);

        for (i = 0; i < N; i = i + 1) begin
            voltages[i] = 0;
            totals[i]   = 0;
            spikes[i]   = 0;
        end
    end

    reg [8:0] neuron_index; 
    wire signed [15:0] new_voltage;
    wire new_spike;

    lif_math neuron_math(
        .old_voltage(voltages[neuron_index]),
        .total(totals[neuron_index]),
        .new_voltage(new_voltage),
        .spike(new_spike)
    );
    
    always @(posedge clk) begin
        if (reset) begin
            neuron_index <= 0;
            busy <= 0;
        end
        else if (!busy) begin
            if(start_step) begin
                busy <= 1;
                neuron_index <= 0;
            end
        end
        else if (busy) begin

            if (neuron_index == N) begin
                busy <=0;
            end
            else begin
                voltages[neuron_index] <= new_voltage;
                spikes[neuron_index] <= new_spike;
                neuron_index <= neuron_index + 1;
            end

        end
    end
endmodule