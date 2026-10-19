module TopModule(
    input  [7:0]    A,
    output [15:0]   B
    );

//*************code***********//

    assign B = ({8'b0, A} << 8) - ({8'b0, A} << 2) - {8'b0, A};
//*************code***********//

endmodule
