import json
from types import MethodType
from unittest.mock import PropertyMock, patch

import pytest
from eth_abi import decode, encode
from eth_utils import keccak
from eth_utils.address import to_checksum_address
from hypothesis import given
from hypothesis.strategies import composite, integers
from starkware.starknet.public.abi import (
    get_selector_from_name,
    get_storage_var_address,
)
from web3._utils.abi import map_abi_data
from web3._utils.normalizers import BASE_RETURN_NORMALIZERS
from web3.exceptions import NoABIFunctionsFound

from kakarot_scripts.ef_tests.fetch import EF_TESTS_PARSED_DIR
from tests.utils.constants import CHAIN_ID, TRANSACTION_GAS_LIMIT, TRANSACTIONS
from tests.utils.errors import cairo_error
from tests.utils.helpers import felt_to_signed_int, rlp_encode_signed_data
from tests.utils.syscall_handler import SyscallHandler, parse_state

CONTRACT_ADDRESS = 1234
OWNER = to_checksum_address(f"0x{0xABDE1:040x}")
OTHER = to_checksum_address(f"0x{0xE1A5:040x}")

EVM_ADDRESS = 0x42069


@pytest.fixture(scope="module")
def get_contract(cairo_run):
    from kakarot_scripts.utils.kakarot import get_contract_sync as get_solidity_contract

    def _factory(contract_app, contract_name):
        def _wrap_cairo_run(fun):
            def _wrapper(self, *args, **kwargs):
                origin = kwargs.pop("origin", 0)
                gas_limit = kwargs.pop("gas_limit", int(TRANSACTION_GAS_LIMIT))
                gas_price = kwargs.pop("gas_price", 0)
                value = kwargs.pop("value", 0)
                data = self.get_function_by_name(fun)(
                    *args, **kwargs
                )._encode_transaction_data()
                evm, state, gas, _ = cairo_run(
                    "eth_call",
                    origin=origin,
                    to=CONTRACT_ADDRESS,
                    gas_limit=gas_limit,
                    gas_price=gas_price,
                    value=value,
                    data=data,
                )
                abi = self.get_function_by_name(fun).abi
                if abi["stateMutability"] not in ["pure", "view"]:
                    return evm, state, gas

                types = [o["type"] for o in abi["outputs"]]
                decoded = decode(types, bytes(evm["return_data"]))
                normalized = map_abi_data(BASE_RETURN_NORMALIZERS, types, decoded)
                return normalized[0] if len(normalized) == 1 else normalized

            return _wrapper

        contract = get_solidity_contract(contract_app, contract_name)
        try:
            for fun in contract.functions:
                setattr(contract, fun, MethodType(_wrap_cairo_run(fun), contract))
        except NoABIFunctionsFound:
            pass

        return contract

    return _factory


class TestKakarot:

    class TestPause:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__pause")

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        @SyscallHandler.patch("Pausable_paused", 0)
        def test_should_pause(self, cairo_run):
            cairo_run("test__pause")
            SyscallHandler.mock_storage.assert_called_with(
                address=get_storage_var_address("Pausable_paused"), value=1
            )

    class TestUnpause:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__unpause")

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        @SyscallHandler.patch("Pausable_paused", 1)
        def test_should_unpause(self, cairo_run):
            cairo_run("test__unpause")
            SyscallHandler.mock_storage.assert_called_with(
                address=get_storage_var_address("Pausable_paused"), value=0
            )

    class TestNativeToken:
        @pytest.mark.slow
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__set_native_token", address=0xABC)

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_set_native_token(self, cairo_run):
            token_address = 0xABCDE12345
            cairo_run("test__set_native_token", address=token_address)
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address("Kakarot_native_token_address"),
                value=token_address,
            )

    class TestTransferOwnership:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__transfer_ownership", new_owner=0xABC)

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_transfer_ownership(self, cairo_run):
            new_owner = 0xABCDE12345
            cairo_run("test__transfer_ownership", new_owner=new_owner)
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address("Ownable_owner"), value=new_owner
            )

    class TestBaseFee:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__set_base_fee", base_fee=0xABC)

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_set_base_fee(self, cairo_run):
            base_fee = 0x100
            cairo_run("test__set_base_fee", base_fee=base_fee)
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address("Kakarot_base_fee"), value=base_fee
            )

    class TestCoinbase:
        @pytest.mark.slow
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__set_coinbase", coinbase=0xABC)

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_set_coinbase(self, cairo_run):
            coinbase = 0xC0DE
            cairo_run("test__set_coinbase", coinbase=coinbase)
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address("Kakarot_coinbase"), value=coinbase
            )

    class TestPrevRandao:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__set_prev_randao", prev_randao=0xABC)

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_set_prev_randao(self, cairo_run):
            prev_randao = 0x123
            cairo_run("test__set_prev_randao", prev_randao=prev_randao)
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address("Kakarot_prev_randao"),
                value=prev_randao,
            )

    class TestInitializeChainId:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__initialize_chain_id", chain_id=0xABC)

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_initialize_chain_id(self, cairo_run):
            chain_id = 0x123

            cairo_run("test__initialize_chain_id", chain_id=chain_id)
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address("Kakarot_chain_id"),
                value=chain_id,
            )

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_fail_initialize_chain_id_twice(self, cairo_run):
            chain_id = 0x123
            with (
                cairo_error(message="Kakarot: chain_id already initialized"),
                SyscallHandler.patch("Kakarot_chain_id", chain_id),
            ):
                cairo_run("test__initialize_chain_id", chain_id=chain_id)

    class TestBlockGasLimit:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__set_block_gas_limit", block_gas_limit=0xABC)

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_set_block_gas_limit(self, cairo_run):
            block_gas_limit = 0x1000
            cairo_run("test__set_block_gas_limit", block_gas_limit=block_gas_limit)
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address("Kakarot_block_gas_limit"),
                value=block_gas_limit,
            )

    class TestAccountContractClassHash:
        @pytest.mark.slow
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__set_account_contract_class_hash", class_hash=0xABC)

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_set_account_contract_class_hash(self, cairo_run):
            class_hash = 0x123
            cairo_run("test__set_account_contract_class_hash", class_hash=class_hash)
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address("Kakarot_account_contract_class_hash"),
                value=class_hash,
            )

    class TestUninitializedAccountClassHash:
        @pytest.mark.slow
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run(
                    "test__set_uninitialized_account_class_hash", class_hash=0xABC
                )

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_set_uninitialized_account_class_hash(self, cairo_run):
            class_hash = 0x123
            cairo_run(
                "test__set_uninitialized_account_class_hash", class_hash=class_hash
            )
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address(
                    "Kakarot_uninitialized_account_class_hash"
                ),
                value=class_hash,
            )

    class TestAuthorizedCairoPrecompileCaller:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run(
                    "test__set_authorized_cairo_precompile_caller",
                    caller_address=0xABC,
                    authorized=0xBCD,
                )

        @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
        def test_should_set_authorized_cairo_precompile_caller(self, cairo_run):
            caller = 0x123
            authorized = 0x456
            cairo_run(
                "test__set_authorized_cairo_precompile_caller",
                caller_address=caller,
                authorized=authorized,
            )
            SyscallHandler.mock_storage.assert_any_call(
                address=get_storage_var_address(
                    "Kakarot_authorized_cairo_precompiles_callers",
                    caller,
                ),
                value=authorized,
            )

    class Cairo1HelpersClass:
        @SyscallHandler.patch("Ownable_owner", 0xDEAD)
        def test_should_assert_only_owner(self, cairo_run):
            with cairo_error(message="Ownable: caller is not the owner"):
                cairo_run("test__set_cairo1_helpers_class_hash", class_hash=0xABC)

    class TestDeployEOA:
        @SyscallHandler.patch("Pausable_paused", 1)
        def test_should_assert_unpaused(self, cairo_run):
            with cairo_error(message="Pausable: paused"):
                cairo_run(
                    "test__deploy_externally_owned_account", evm_address=EVM_ADDRESS
                )

    class TestRegisterAccount:
        @SyscallHandler.patch("Pausable_paused", 1)
        def test_should_assert_unpaused(self, cairo_run):
            with cairo_error(message="Pausable: paused"):
                cairo_run("test__register_account", evm_address=EVM_ADDRESS)

        @SyscallHandler.patch("Kakarot_evm_to_starknet_address", EVM_ADDRESS, 0)
        @patch(
            "tests.utils.syscall_handler.SyscallHandler.caller_address",
            new_callable=PropertyMock,
        )
        def test_register_account_should_store_evm_to_starknet_address_mapping(
            self, mock_caller_address, cairo_run
        ):
            starknet_address = cairo_run(
                "compute_starknet_address", evm_address=EVM_ADDRESS
            )
            mock_caller_address.return_value = starknet_address

            cairo_run("test__register_account", evm_address=EVM_ADDRESS)

            SyscallHandler.mock_storage.assert_called_with(
                address=get_storage_var_address(
                    "Kakarot_evm_to_starknet_address", EVM_ADDRESS
                ),
                value=starknet_address,
            )

        @pytest.mark.slow
        @SyscallHandler.patch("Kakarot_evm_to_starknet_address", 0x42069, 1)
        @patch(
            "tests.utils.syscall_handler.SyscallHandler.caller_address",
            new_callable=PropertyMock,
        )
        def test_register_account_should_fail_existing_entry(
            self, mock_caller_address, cairo_run
        ):
            starknet_address = cairo_run(
                "compute_starknet_address", evm_address=EVM_ADDRESS
            )
            mock_caller_address.return_value = starknet_address

            with cairo_error(message="Kakarot: account already registered"):
                cairo_run("test__register_account", evm_address=EVM_ADDRESS)

        @SyscallHandler.patch("Kakarot_evm_to_starknet_address", EVM_ADDRESS, 0)
        @patch(
            "tests.utils.syscall_handler.SyscallHandler.caller_address",
            new_callable=PropertyMock,
        )
        def test_register_account_should_fail_caller_not_resolved_address(
            self, mock_caller_address, cairo_run
        ):
            expected_starknet_address = cairo_run(
                "compute_starknet_address", evm_address=EVM_ADDRESS
            )
            mock_caller_address.return_value = expected_starknet_address // 2

            with cairo_error(
                message=f"Kakarot: Caller should be {felt_to_signed_int(expected_starknet_address)}, got {expected_starknet_address // 2}"
            ):
                cairo_run("test__register_account", evm_address=EVM_ADDRESS)

        class TestUpgradeAccount:
            @SyscallHandler.patch("Ownable_owner", 0xDEAD)
            def test_should_assert_only_owner(self, cairo_run):
                with cairo_error(message="Ownable: caller is not the owner"):
                    cairo_run(
                        "test__upgrade_account",
                        evm_address=EVM_ADDRESS,
                        new_class_hash=0x1234,
                    )

            @SyscallHandler.patch(
                "Kakarot_evm_to_starknet_address", EVM_ADDRESS, 0x99999
            )
            @SyscallHandler.patch("Ownable_owner", SyscallHandler.caller_address)
            @SyscallHandler.patch("IAccount.upgrade", lambda *_: [])
            def test_upgrade_account_should_replace_class(self, cairo_run):
                cairo_run(
                    "test__upgrade_account",
                    evm_address=EVM_ADDRESS,
                    new_class_hash=0x1234,
                )
                SyscallHandler.mock_call.assert_called_with(
                    contract_address=0x99999,
                    function_selector=get_selector_from_name("upgrade"),
                    calldata=[0x1234],
                )

    class TestL1Handler:
        @SyscallHandler.patch("Pausable_paused", 1)
        def test_should_assert_unpaused(self, cairo_run):
            with cairo_error(message="Pausable: paused"):
                cairo_run(
                    "test__handle_l1_message",
                    from_address=0xABC,
                    l1_sender=0xABC,
                    to_address=0xABC,
                    value=0xABC,
                    data=[],
                )

        def test_should_not_handle_message_from_non_l1_messaging_contract(
            self, cairo_run
        ):
            """
            Test that the L1 handler does not handle messages when from_address is not the L1
            messaging contract address (default is address 0).
            If the message were handled, this would fail because no patches are set (e.g. balanceOf,
            deploy, all the IAccount interface methods).
            """
            cairo_run(
                "test__handle_l1_message",
                from_address=0xDEAD,
                l1_sender=0xABDE1,
                to_address=0xABDE1,
                value=0x1234,
                data=[],
            )

    class TestEthCall:
        @pytest.mark.slow
        @pytest.mark.SolmateERC20
        @SyscallHandler.patch("IAccount.is_valid_jumpdest", lambda *_: [1])
        @SyscallHandler.patch("IAccount.get_code_hash", lambda *_: [0x1, 0x1])
        def test_erc20_transfer(self, get_contract):
            erc20 = get_contract("Solmate", "ERC20")
            amount = int(1e18)
            initial_state = {
                CONTRACT_ADDRESS: {
                    "code": list(erc20.bytecode_runtime),
                    "storage": {
                        "0x2": amount,
                        keccak(encode(["address", "uint8"], [OWNER, 3])).hex(): amount,
                    },
                    "balance": 0,
                    "nonce": 0,
                }
            }
            with SyscallHandler.patch_state(parse_state(initial_state)):
                evm, *_ = erc20.transfer(OTHER, amount, origin=int(OWNER, 16))
            assert not evm["reverted"]

        @pytest.mark.slow
        @pytest.mark.SolmateERC721
        @SyscallHandler.patch("IAccount.is_valid_jumpdest", lambda *_: [1])
        @SyscallHandler.patch("IAccount.get_code_hash", lambda *_: [0x1, 0x1])
        def test_erc721_transfer(self, get_contract):
            erc721 = get_contract("Solmate", "ERC721")
            token_id = 1337
            initial_state = {
                CONTRACT_ADDRESS: {
                    "code": list(erc721.bytecode_runtime),
                    "storage": {
                        keccak(encode(["uint256", "uint8"], [token_id, 2])).hex(): int(
                            OWNER, 16
                        ),
                        keccak(encode(["address", "uint8"], [OWNER, 3])).hex(): 1,
                    },
                    "balance": 0,
                    "nonce": 0,
                }
            }
            with SyscallHandler.patch_state(parse_state(initial_state)):
                evm, *_ = erc721.transferFrom(
                    OWNER, OTHER, token_id, origin=int(OWNER, 16)
                )
            assert not evm["reverted"]

        @pytest.mark.slow
        @pytest.mark.NoCI
        @pytest.mark.EFTests
        @pytest.mark.parametrize(
            "ef_blockchain_test",
            EF_TESTS_PARSED_DIR.glob("*walletConstruction_d0g1v0_Cancun*.json"),
        )
        def test_case(
            self,
            cairo_run,
            ef_blockchain_test,
        ):
            test_case = json.loads(ef_blockchain_test.read_text())
            block = test_case["blocks"][0]
            tx = block["transactions"][0]
            with SyscallHandler.patch_state(parse_state(test_case["pre"])):
                evm, state, gas_used, required_gas = cairo_run(
                    "eth_call",
                    origin=int(tx["sender"], 16),
                    to=int(tx.get("to"), 16) if tx.get("to") else None,
                    gas_limit=int(tx["gasLimit"], 16),
                    gas_price=int(tx["gasPrice"], 16),
                    value=int(tx["value"], 16),
                    data=tx["data"],
                    nonce=int(tx["nonce"], 16),
                )

            parsed_state = {
                int(address, 16): {
                    "balance": int(account["balance"], 16),
                    "code": account["code"],
                    "nonce": account["nonce"],
                    "storage": {
                        key: int(value, 16)
                        for key, value in account["storage"].items()
                        if int(value, 16) > 0
                    },
                }
                for address, account in state["accounts"].items()
                if int(address, 16) > 10
            }
            assert parsed_state == parse_state(test_case["postState"])
            assert gas_used == int(block["blockHeader"]["gasUsed"], 16)

        @pytest.mark.skip
        def test_failing_contract(self, cairo_run):
            initial_state = {
                CONTRACT_ADDRESS: {
                    "code": bytes.fromhex("ADDC0DE1"),
                    "storage": {},
                    "balance": 0,
                    "nonce": 0,
                }
            }
            with SyscallHandler.patch_state(parse_state(initial_state)):
                evm, *_ = cairo_run(
                    "eth_call",
                    origin=int(OWNER, 16),
                    to=CONTRACT_ADDRESS,
                    gas_limit=0,
                    gas_price=0,
                    value=0,
                    data="0xADD_DATA",
                )
            assert not evm["reverted"]

        @SyscallHandler.patch("IAccount.is_valid_jumpdest", lambda *_: [1])
        @SyscallHandler.patch("IAccount.get_code_hash", lambda *_: [0x1, 0x1])
        @SyscallHandler.patch("IERC20.balanceOf", lambda *_: [0x1, 0x1])
        def test_create_tx_returndata_should_be_20_bytes_evm_address(self, cairo_run):
            """
            Bug reported by Protofire for the simulation of the create tx using eth_call.
            https://github.com/safe-global/safe-singleton-factory.
            """
            evm, _, _, _ = cairo_run(
                "eth_call",
                origin=0xE1CB04A0FA36DDD16A06EA828007E35E1A3CBC37,
                to=None,
                gas_limit=1000000,
                gas_price=100,
                value=0,
                data="604580600e600039806000f350fe7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe03601600081602082378035828234f58015156039578182fd5b8082525050506014600cf3",
            )
            assert (
                "2fa86add0aed31f33a762c9d88e807c475bd51d0f52bd0955754b2608f7e4989"
                == keccak(bytes(evm["return_data"])).hex()
            )

    class TestEthChainIdEntrypoint:
        @given(chain_id=integers(min_value=0, max_value=2**64 - 1))
        def test_should_return_chain_id(self, cairo_run, chain_id):
            with (
                patch.dict(SyscallHandler.tx_info, {"chain_id": chain_id}),
                SyscallHandler.patch("Kakarot_chain_id", chain_id),
            ):
                res = cairo_run("test__eth_chain_id")
                assert res == chain_id

    class TestEthSendRawTransactionEntrypoint:
        @SyscallHandler.patch("Pausable_paused", 1)
        def test_should_assert_unpaused(self, cairo_run):
            with cairo_error(message="Pausable: paused"):
                cairo_run("test__eth_send_raw_unsigned_tx", tx_data_len=0, tx_data=[])

        def test_should_raise_invalid_chain_id_tx_type_different_from_0(
            self, cairo_run
        ):
            transaction = {
                "type": 2,
                "gas": 100_000,
                "maxFeePerGas": 2_000_000_000,
                "maxPriorityFeePerGas": 2_000_000_000,
                "data": "0x616263646566",
                "nonce": 34,
                "to": "",
                "value": 0x00,
                "accessList": [],
                "chainId": 9999,
            }
            tx_data = list(rlp_encode_signed_data(transaction))

            with cairo_error(message="Invalid chain id"):
                cairo_run(
                    "test__eth_send_raw_unsigned_tx",
                    tx_data_len=len(tx_data),
                    tx_data=tx_data,
                )

        @SyscallHandler.patch("IAccount.get_nonce", lambda *_: [1])
        @SyscallHandler.patch("Kakarot_chain_id", CHAIN_ID)
        @pytest.mark.parametrize("tx", TRANSACTIONS)
        def test_should_raise_invalid_nonce(self, cairo_run, tx):
            # explicitly set the nonce in transaction to be different from the patch
            tx = {**tx, "nonce": 0}
            tx_data = list(rlp_encode_signed_data(tx))
            with cairo_error(message="Invalid nonce"):
                cairo_run(
                    "test__eth_send_raw_unsigned_tx",
                    tx_data_len=len(tx_data),
                    tx_data=tx_data,
                )

        @SyscallHandler.patch("Kakarot_chain_id", CHAIN_ID)
        @SyscallHandler.patch("IAccount.get_nonce", lambda *_: [34])
        @given(gas_limit=integers(min_value=2**64, max_value=2**248 - 1))
        def test_raise_gas_limit_too_high(self, cairo_run, gas_limit):
            tx = {
                "type": 2,
                "gas": gas_limit,
                "maxFeePerGas": 2_000_000_000,
                "maxPriorityFeePerGas": 3_000_000_000,
                "data": "0x616263646566",
                "nonce": 34,
                "to": "0x09616C3d61b3331fc4109a9E41a8BDB7d9776609",
                "value": 0x5AF3107A4000,
                "accessList": [],
                "chainId": CHAIN_ID,
            }
            tx_data = list(rlp_encode_signed_data(tx))

            with cairo_error(message="Gas limit too high"):
                cairo_run(
                    "test__eth_send_raw_unsigned_tx",
                    tx_data_len=len(tx_data),
                    tx_data=tx_data,
                )

        @SyscallHandler.patch("Kakarot_chain_id", CHAIN_ID)
        @SyscallHandler.patch("IAccount.get_nonce", lambda *_: [34])
        @given(maxFeePerGas=integers(min_value=2**128, max_value=2**248 - 1))
        def test_raise_max_fee_per_gas_too_high(self, cairo_run, maxFeePerGas):
            tx = {
                "type": 2,
                "gas": 100_000,
                "maxFeePerGas": maxFeePerGas,
                "maxPriorityFeePerGas": 3_000_000_000,
                "data": "0x616263646566",
                "nonce": 34,
                "to": "0x09616C3d61b3331fc4109a9E41a8BDB7d9776609",
                "value": 0x5AF3107A4000,
                "accessList": [],
                "chainId": CHAIN_ID,
            }
            tx_data = list(rlp_encode_signed_data(tx))

            with cairo_error(message="Max fee per gas too high"):
                cairo_run(
                    "test__eth_send_raw_unsigned_tx",
                    tx_data_len=len(tx_data),
                    tx_data=tx_data,
                )

        @SyscallHandler.patch("Kakarot_chain_id", CHAIN_ID)
        @pytest.mark.parametrize("tx", TRANSACTIONS)
        def test_raise_transaction_gas_limit_too_high(self, cairo_run, tx):
            tx_data = list(rlp_encode_signed_data(tx))

            with (
                SyscallHandler.patch("IAccount.get_nonce", lambda *_: [tx["nonce"]]),
                cairo_error(message="Transaction gas_limit > Block gas_limit"),
            ):
                cairo_run(
                    "test__eth_send_raw_unsigned_tx",
                    tx_data_len=len(tx_data),
                    tx_data=tx_data,
                )

        @SyscallHandler.patch("Kakarot_block_gas_limit", TRANSACTION_GAS_LIMIT)
        @SyscallHandler.patch("Kakarot_base_fee", TRANSACTION_GAS_LIMIT * 10**10)
        @SyscallHandler.patch("Kakarot_chain_id", CHAIN_ID)
        @pytest.mark.parametrize("tx", TRANSACTIONS)
        def test_raise_max_fee_per_gas_too_low(self, cairo_run, tx):
            tx_data = list(rlp_encode_signed_data(tx))

            with (
                SyscallHandler.patch("IAccount.get_nonce", lambda *_: [tx["nonce"]]),
                cairo_error(message="Max fee per gas too low"),
            ):
                cairo_run(
                    "test__eth_send_raw_unsigned_tx",
                    tx_data_len=len(tx_data),
                    tx_data=tx_data,
                )

        @composite
        def max_priority_fee_too_high(draw):
            max_fee_per_gas = draw(integers(min_value=0, max_value=2**128 - 2))
            max_priority_fee_per_gas = draw(
                integers(min_value=max_fee_per_gas + 1, max_value=2**248 - 1)
            )
            return (max_fee_per_gas, max_priority_fee_per_gas)

        @SyscallHandler.patch("Kakarot_block_gas_limit", TRANSACTION_GAS_LIMIT)
        @SyscallHandler.patch("IAccount.get_nonce", lambda *_: [34])
        @SyscallHandler.patch("Kakarot_chain_id", CHAIN_ID)
        @given(max_priority_fee_too_high())
        def test_raise_max_priority_fee_too_high(
            self, cairo_run, max_priority_fee_too_high
        ):
            tx = {
                "type": 2,
                "gas": 100_000,
                "maxFeePerGas": max_priority_fee_too_high[0],
                "maxPriorityFeePerGas": max_priority_fee_too_high[1],
                "data": "0x616263646566",
                "nonce": 34,
                "to": "0x09616C3d61b3331fc4109a9E41a8BDB7d9776609",
                "value": 0x5AF3107A4000,
                "accessList": [],
                "chainId": CHAIN_ID,
            }
            tx_data = list(rlp_encode_signed_data(tx))

            with cairo_error(message="Max priority fee greater than max fee per gas"):
                cairo_run(
                    "test__eth_send_raw_unsigned_tx",
                    tx_data_len=len(tx_data),
                    tx_data=tx_data,
                )

        @SyscallHandler.patch("IERC20.balanceOf", lambda *_: [0, 0])
        @SyscallHandler.patch("Kakarot_block_gas_limit", TRANSACTION_GAS_LIMIT)
        @SyscallHandler.patch("IAccount.get_evm_address", lambda *_: [0xABDE1])
        @SyscallHandler.patch("Kakarot_chain_id", CHAIN_ID)
        @pytest.mark.parametrize("tx", TRANSACTIONS)
        def test_raise_not_enough_ETH_balance(self, cairo_run, tx):
            tx_data = list(rlp_encode_signed_data(tx))

            with (
                SyscallHandler.patch("IAccount.get_nonce", lambda *_: [tx["nonce"]]),
                cairo_error(message="Not enough ETH to pay msg.value + max gas fees"),
            ):
                cairo_run(
                    "test__eth_send_raw_unsigned_tx",
                    tx_data_len=len(tx_data),
                    tx_data=tx_data,
                )

    class TestLoopProfiling:
        @pytest.mark.slow
        @pytest.mark.NoCI
        @SyscallHandler.patch("IAccount.is_valid_jumpdest", lambda *_: [1])
        @SyscallHandler.patch("IAccount.get_code_hash", lambda *_: [0x1, 0x1])
        @pytest.mark.parametrize("steps", [10, 50, 100, 200])
        def test_loop_profiling(self, get_contract, steps):
            plain_opcodes = get_contract("PlainOpcodes", "PlainOpcodes")
            initial_state = {
                CONTRACT_ADDRESS: {
                    "code": list(plain_opcodes.bytecode_runtime),
                    "storage": {},
                    "balance": 0,
                    "nonce": 0,
                }
            }
            with SyscallHandler.patch_state(parse_state(initial_state)):
                res = plain_opcodes.loopProfiling(steps)
            assert res == sum(x for x in range(steps))
