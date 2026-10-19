module TopModule(
    input       [3:0]       A_in  ,
    input       [3:0]       B_in  ,
    input                   C_1   ,
  
    output   wire           CO    ,
    output   wire [3:0]     S
);
    wire [3:0] G, P, C;
    wire c0_and, c1_and, c2_and, c3_and;

    xor (P[0], A_in[0], B_in[0]);
    xor (P[1], A_in[1], B_in[1]);
    xor (P[2], A_in[2], B_in[2]);
    xor (P[3], A_in[3], B_in[3]);

    and (G[0], A_in[0], B_in[0]);
    and (G[1], A_in[1], B_in[1]);
    and (G[2], A_in[2], B_in[2]);
    and (G[3], A_in[3], B_in[3]);

    and (c0_and, P[0], C_1);
    or  (C[0], G[0], c0_and);

    and (c1_and, P[1], C[0]);
    or  (C[1], G[1], c1_and);

    and (c2_and, P[2], C[1]);
    or  (C[2], G[2], c2_and);

    and (c3_and, P[3], C[2]);
    or  (C[3], G[3], c3_and);

    xor (S[0], P[0], C_1);
    xor (S[1], P[1], C[0]);
    xor (S[2], P[2], C[1]);
    xor (S[3], P[3], C[2]);

    buf (CO, C[3]);
    
endmodule
