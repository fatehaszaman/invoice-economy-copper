% Four-flow consistency as a type system.
%
% China's State Taxation Administration organises invoice compliance around
% whether invoice, goods, funds, and business activity correspond to one
% another. That is, in data terms, the question of what real-world object a
% row represents. Two independent parties -- a national tax authority and
% this data model -- concluding that these are four different objects is the
% quietest argument in this repository.

:- discontiguous economic_object/1.

% ---------------------------------------------------------------- objects

economic_object(invoice_event).
economic_object(business_transaction).
economic_object(ownership_transfer).
economic_object(funds_transfer).
economic_object(financing_event).
economic_object(physical_movement).
economic_object(inventory_state).
economic_object(production_event).
economic_object(consumption_event).
economic_object(import_event).
economic_object(export_event).
economic_object(price_observation).

% Which objects carry physical tonnage.
carries_tonnage(physical_movement).
carries_tonnage(inventory_state).
carries_tonnage(production_event).
carries_tonnage(consumption_event).
carries_tonnage(import_event).
carries_tonnage(export_event).

% Only consumption terminates a tonne's life. Everything else may recur
% arbitrarily for the same physical metal. Conflating recurring and terminal
% events is exactly how "demand" becomes ambiguous.
terminal(consumption_event).
recurring(O) :- economic_object(O), \+ terminal(O).

% ----------------------------------------------------------- relationships

supports(invoice_event, business_transaction).
may_have(business_transaction, physical_movement).
changes(physical_movement, inventory_state).
consumes(production_event, inventory_state).

% The two load-bearing negative rules.
does_not_imply(ownership_transfer, consumption_event).
does_not_imply(invoice_event, physical_movement).

% ------------------------------------------------------- legal aggregation

% Two records may be summed only if they represent the same object type.
aggregatable(A, B) :- A == B, economic_object(A).

violation(mixed_aggregation(A,B)) :-
    economic_object(A), economic_object(B),
    \+ aggregatable(A, B).

% A "demand" figure built from title transfers is a category error.
violation(demand_from_title(N)) :-
    aggregated_as_demand(N, ownership_transfer).

% An invoice with no corresponding physical counterpart is flagged, NOT
% removed. The premise of this project is that such disagreement may be
% information rather than error.
flag(invoice_without_physical(Id)) :-
    record(Id, invoice_event, _),
    \+ ( record(_, physical_movement, Id) ).
