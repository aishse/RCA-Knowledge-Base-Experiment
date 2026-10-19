module TopModule(
	input clk,
	input rst_n,
	input a,
	output match
	);

	reg [8:0] a_tem;
	reg match_f;
	reg match_b;
	wire [8:0] next_a_tem;

	assign next_a_tem = {a_tem[7:0], a};
	
	always @(posedge clk or negedge rst_n)
		if (!rst_n)
			begin 
				a_tem <= 9'b0;
				match_f <= 1'b0;
				match_b <= 1'b0;
			end
		else
			begin
				a_tem <= next_a_tem;
				match_f <= (next_a_tem[8:6] == 3'b011);
				match_b <= (next_a_tem[2:0] == 3'b110);
			end
			
	assign match = match_b && match_f;
endmodule
