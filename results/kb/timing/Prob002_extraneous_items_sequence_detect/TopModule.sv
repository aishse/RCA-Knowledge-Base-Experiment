module TopModule(
	input clk,
	input rst_n,
	input a,
	output match
	);

	reg [8:0] a_tem;
	reg match_b;

	always @(posedge clk or negedge rst_n)
		if (!rst_n)
			begin
				a_tem <= 9'b0;
				match_b <= 1'b0;
			end
		else
			begin
				a_tem <= {a_tem[7:0], a};
				match_b <= (({a_tem[7:0], a} & 9'b111000111) == 9'b011000110);
			end

	assign match = match_b;
endmodule
