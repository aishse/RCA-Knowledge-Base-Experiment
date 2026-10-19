module TopModule(
	input clk,
	input rst_n,
	input a,
	output match
	);

	reg [8:0] a_tem;
	reg match_b;
	wire [8:0] a_next;

	assign a_next = {a_tem[7:0], a};

	always @(posedge clk or negedge rst_n)
		if (!rst_n)
			begin 
				a_tem <= 9'b0;
				match_b <= 1'b0;
			end
		else
			begin
				a_tem <= a_next;
				match_b <= (a_next[8:6] == 3'b011) && (a_next[2:0] == 3'b110);
			end
			
	assign match = match_b;
endmodule
