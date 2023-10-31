// SPDX-License-Identifier: MIT

%lang starknet

// Starkware dependencies

from starkware.cairo.common.cairo_builtins import HashBuiltin, BitwiseBuiltin
from starkware.cairo.common.math_cmp import is_in_range, is_le
from starkware.cairo.common.math import split_felt
from starkware.cairo.common.bool import FALSE, TRUE
from starkware.starknet.common.syscalls import get_block_number, get_block_timestamp
from starkware.cairo.common.uint256 import Uint256

// Internal dependencies
from kakarot.constants import Constants, native_token_address, blockhash_registry_address
from kakarot.execution_context import ExecutionContext
from kakarot.interfaces.interfaces import IBlockhashRegistry
from kakarot.model import model
from kakarot.stack import Stack
from kakarot.state import State
from kakarot.errors import Errors
from utils.utils import Helpers

// @title BlockInformation information opcodes.
// @notice This file contains the functions to execute for block information opcodes.
namespace BlockInformation {
    // Define constants.
    const GAS_COST_BLOCKHASH = 20;
    const GAS_COST_COINBASE = 2;
    const GAS_COST_TIMESTAMP = 2;
    const GAS_COST_NUMBER = 2;
    const GAS_COST_DIFFICULTY = 2;
    const GAS_COST_GASLIMIT = 2;
    const GAS_COST_CHAINID = 2;
    const GAS_COST_SELFBALANCE = 5;
    const GAS_COST_BASEFEE = 2;

    // @notice COINBASE operation.
    // @dev Get the hash of one of the 256 most recent complete blocks.
    // @dev 0 if the block number is not in the valid range.
    // @custom:since Frontier
    // @custom:group Block Information
    // @custom:gas 20
    // @custom:stack_consumed_elements 1
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_blockhash{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        alloc_locals;
        if (ctx.stack.size == 0) {
            let (revert_reason_len, revert_reason) = Errors.stackUnderflow();
            let ctx = ExecutionContext.stop(ctx, revert_reason_len, revert_reason, TRUE);
            return ctx;
        }

        // Get the blockNumber
        let (stack, block_number_uint256) = Stack.pop(ctx.stack);
        let block_number = block_number_uint256.low;

        // Check if blockNumber is within bounds by checking with current block number
        // Valid range is the last 256 blocks (not including the current one)
        let (local current_block_number: felt) = get_block_number();
        let in_range = is_in_range(block_number, current_block_number - 256, current_block_number);

        // If not in range, return 0
        if (in_range == FALSE) {
            tempvar blockhash = new Uint256(0, 0);
            tempvar syscall_ptr = syscall_ptr;
            tempvar pedersen_ptr = pedersen_ptr;
            tempvar range_check_ptr = range_check_ptr;
            tempvar bitwise_ptr = bitwise_ptr;
        } else {
            let (blockhash_registry_address_: felt) = blockhash_registry_address.read();
            let (blockhash_: felt) = IBlockhashRegistry.get_blockhash(
                contract_address=blockhash_registry_address_, block_number=[block_number_uint256]
            );
            let blockhash = Helpers.to_uint256(blockhash_);
            tempvar syscall_ptr = syscall_ptr;
            tempvar pedersen_ptr = pedersen_ptr;
            tempvar range_check_ptr = range_check_ptr;
            tempvar bitwise_ptr = bitwise_ptr;
        }

        let stack = Stack.push(stack, blockhash);

        let ctx = ExecutionContext.update_stack(ctx, stack);
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_BLOCKHASH);
        return ctx;
    }

    // @notice COINBASE operation.
    // @dev Get the block's beneficiary address.
    // @custom:since Frontier
    // @custom:group Block Information
    // @custom:gas 2
    // @custom:stack_consumed_elements 0
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_coinbase{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        // Get the coinbase address.

        if (ctx.stack.size == Constants.STACK_MAX_DEPTH) {
            let (revert_reason_len, revert_reason) = Errors.stackOverflow();
            let ctx = ExecutionContext.stop(ctx, revert_reason_len, revert_reason, TRUE);
            return ctx;
        }

        let coinbase_address = Helpers.to_uint256(val=Constants.MOCK_COINBASE_ADDRESS);
        let stack: model.Stack* = Stack.push(self=ctx.stack, element=coinbase_address);

        // Update the execution context.
        // Update context stack.
        let ctx = ExecutionContext.update_stack(ctx, stack);
        // Increment gas used.
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_COINBASE);
        return ctx;
    }

    // @notice TIMESTAMP operation.
    // @dev Get the block’s timestamp
    // @custom:since Frontier
    // @custom:group Block Information
    // @custom:gas 2
    // @custom:stack_consumed_elements 0
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_timestamp{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        alloc_locals;

        if (ctx.stack.size == Constants.STACK_MAX_DEPTH) {
            let (revert_reason_len, revert_reason) = Errors.stackOverflow();
            let ctx = ExecutionContext.stop(ctx, revert_reason_len, revert_reason, TRUE);
            return ctx;
        }

        // Get the block’s timestamp
        let (current_timestamp) = get_block_timestamp();
        let block_timestamp = Helpers.to_uint256(val=current_timestamp);

        let stack: model.Stack* = Stack.push(self=ctx.stack, element=block_timestamp);

        // Update the execution context.
        // Update context stack.
        let ctx = ExecutionContext.update_stack(ctx, stack);
        // Increment gas used.
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_TIMESTAMP);
        return ctx;
    }

    // @notice NUMBER operation.
    // @dev Get the block number
    // @custom:since Frontier
    // @custom:group Block Information
    // @custom:gas 2
    // @custom:stack_consumed_elements 0
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_number{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        alloc_locals;

        if (ctx.stack.size == Constants.STACK_MAX_DEPTH) {
            let (revert_reason_len, revert_reason) = Errors.stackOverflow();
            let ctx = ExecutionContext.stop(ctx, revert_reason_len, revert_reason, TRUE);
            return ctx;
        }

        // Get the block number.
        let (current_block) = get_block_number();
        let block_number = Helpers.to_uint256(val=current_block);

        let stack: model.Stack* = Stack.push(self=ctx.stack, element=block_number);

        // Update the execution context.
        // Update context stack.
        let ctx = ExecutionContext.update_stack(ctx, stack);
        // Increment gas used.
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_NUMBER);
        return ctx;
    }

    // @notice DIFFICULTY operation.
    // @dev Get Difficulty
    // @custom:since Frontier
    // @custom:group Block Information
    // @custom:gas 2
    // @custom:stack_consumed_elements 0
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_difficulty{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        if (ctx.stack.size == Constants.STACK_MAX_DEPTH) {
            let (revert_reason_len, revert_reason) = Errors.stackOverflow();
            let ctx = ExecutionContext.stop(ctx, revert_reason_len, revert_reason, TRUE);
            return ctx;
        }

        // Get the Difficulty.
        let stack: model.Stack* = Stack.push_uint128(ctx.stack, 0);

        // Update the execution context.
        // Update context stack.
        let ctx = ExecutionContext.update_stack(ctx, stack);
        // Increment gas used.
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_DIFFICULTY);
        return ctx;
    }

    // @notice GASLIMIT operation.
    // @dev Get gas limit
    // @custom:since Frontier
    // @custom:group Block Information
    // @custom:gas 2
    // @custom:stack_consumed_elements 0
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_gaslimit{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        // Get the Gas Limit

        if (ctx.stack.size == Constants.STACK_MAX_DEPTH) {
            let (revert_reason_len, revert_reason) = Errors.stackOverflow();
            let ctx = ExecutionContext.stop(ctx, revert_reason_len, revert_reason, TRUE);
            return ctx;
        }

        let gas_limit = Helpers.to_uint256(val=ctx.call_context.gas_limit);
        let stack: model.Stack* = Stack.push(self=ctx.stack, element=gas_limit);

        // Update the execution context.
        // Update context stack.
        let ctx = ExecutionContext.update_stack(ctx, stack);
        // Increment gas used.
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_GASLIMIT);
        return ctx;
    }

    // @notice CHAINID operation.
    // @dev Get the chain ID.
    // @custom:since Instanbul
    // @custom:group Block Information
    // @custom:gas 2
    // @custom:stack_consumed_elements 0
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_chainid{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        // Get the chain ID.

        if (ctx.stack.size == Constants.STACK_MAX_DEPTH) {
            let (revert_reason_len, revert_reason) = Errors.stackOverflow();
            let ctx = ExecutionContext.stop(ctx, revert_reason_len, revert_reason, TRUE);
            return ctx;
        }

        let stack: model.Stack* = Stack.push_uint128(ctx.stack, Constants.CHAIN_ID);

        // Update the execution context.
        // Update context stack.
        let ctx = ExecutionContext.update_stack(ctx, stack);
        // Increment gas used.
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_CHAINID);
        return ctx;
    }

    // @notice SELFBALANCE operation.
    // @dev Get balance of currently executing contract
    // @custom:since Istanbul
    // @custom:group Block Information
    // @custom:gas 5
    // @custom:stack_consumed_elements 0
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_selfbalance{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        alloc_locals;
        // Get balance of current executing contract address balance and push to stack.
        if (ctx.stack.size == Constants.STACK_MAX_DEPTH) {
            let (revert_reason_len, revert_reason) = Errors.stackOverflow();
            let ctx = ExecutionContext.stop(ctx, revert_reason_len, revert_reason, TRUE);
            return ctx;
        }

        let (state, balance) = State.read_balance(ctx.state, ctx.call_context.address);
        tempvar item = new Uint256(balance.low, balance.high);
        let stack = Stack.push(ctx.stack, item);

        // Update the execution context.
        let ctx = ExecutionContext.update_stack(ctx, stack);
        let ctx = ExecutionContext.update_state(ctx, state);
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_SELFBALANCE);
        return ctx;
    }

    // @notice BASEFEE operation.
    // @dev Get base fee
    // @custom:since Frontier
    // @custom:group Block Information
    // @custom:gas 2
    // @custom:stack_consumed_elements 0
    // @custom:stack_produced_elements 1
    // @param ctx The pointer to the execution context
    // @return ExecutionContext The pointer to the updated execution context.
    func exec_basefee{
        syscall_ptr: felt*,
        pedersen_ptr: HashBuiltin*,
        range_check_ptr,
        bitwise_ptr: BitwiseBuiltin*,
    }(ctx: model.ExecutionContext*) -> model.ExecutionContext* {
        // Get the base fee.

        let stack = Stack.push_uint128(self=ctx.stack, element=0);

        let ctx = ExecutionContext.update_stack(ctx, stack);
        let ctx = ExecutionContext.increment_gas_used(self=ctx, inc_value=GAS_COST_BASEFEE);

        return ctx;
    }
}
