module TopModule(
   input   clk,
   input   rst_n,

   output  reg [3:0] gray_out
);
reg        cycle_hold;
wire [3:0] gray_wire;
wire [3:0] bin_from_gray;
wire [3:0] bin_add_wire;

assign bin_from_gray[3] = gray_out[3];
assign bin_from_gray[2] = gray_out[3] ^ gray_out[2];
assign bin_from_gray[1] = gray_out[3] ^ gray_out[2] ^ gray_out[1];
assign bin_from_gray[0] = gray_out[3] ^ gray_out[2] ^ gray_out[1] ^ gray_out[0];
assign bin_add_wire = bin_from_gray + 4'b0001;
assign gray_wire = (bin_add_wire >> 1) ^ bin_add_wire;

always @(posedge clk or negedge rst_n) begin
   if (rst_n == 1'b0) begin
      gray_out   <= 4'b0;
      cycle_hold <= 1'b0;
   end
   else begin
      cycle_hold <= ~cycle_hold;
      if (cycle_hold == 1'b1) begin
         gray_out <= gray_wire;
      end
   end
end
endmodule
