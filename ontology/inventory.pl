% Stock states and the double-count boundary.
%
% A tonne of copper in China occupies exactly ONE state at a time.
% Summing across states double-counts the same metal.

state(bonded).             % pre-customs, VAT-exempt
state(customs_declared).
state(on_warrant).         % SHFE deliverable
state(off_warrant).        % reported private inventory
state(in_transit).
state(at_fabricator).
state(consumed).           % terminal

transition(bonded,            customs_declared).
transition(customs_declared,  on_warrant).
transition(customs_declared,  off_warrant).
transition(on_warrant,        off_warrant).
transition(off_warrant,       in_transit).
transition(on_warrant,        in_transit).
transition(in_transit,        at_fabricator).
transition(at_fabricator,     consumed).

% consumed has no outbound edge.
terminal_state(consumed).
violation(illegal_transition(A,B)) :-
    state(A), state(B), \+ transition(A,B), A \== B.

% VAT treatment follows from state, and the comparison is refused rather
% than computed wrongly when the treatment differs.
vat_exempt(bonded).
violation(vat_mismatch(A,B)) :-
    state(A), state(B), vat_exempt(A), \+ vat_exempt(B).

% Summing across distinct states is a double count.
violation(double_count(A,B)) :-
    state(A), state(B), A \== B, summed_together(A,B).
