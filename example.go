package main

import (
	"fmt"
	"os"
	"time"

	"github.com/InjectiveLabs/sdk-go/client/common"

	rpchttp "github.com/tendermint/tendermint/rpc/client/http"

	proposaltypes "github.com/InjectiveLabs/sdk-go/chain/exchange/types"
	chainclient "github.com/InjectiveLabs/sdk-go/client/chain"
	sdktypes "github.com/cosmos/cosmos-sdk/types"
)

func main() {
	// network := common.LoadNetwork("mainnet", "k8s")
	network := common.LoadNetwork("testnet", "k8s")
	tmRPC, err := rpchttp.New(network.TmEndpoint, "/websocket")

	if err != nil {
		fmt.Println(err)
	}

	senderAddress, cosmosKeyring, err := chainclient.InitCosmosKeyring(
		os.Getenv("HOME")+"/.injectived",
		"injectived",
		"file",
		"inj-user",
		"12345678",
		"", // keyring will be used if pk not provided
		false,
	)

	if err != nil {
		panic(err)
	}

	clientCtx, err := chainclient.NewClientContext(
		network.ChainId,
		senderAddress.String(),
		cosmosKeyring,
	)

	if err != nil {
		fmt.Println(err)
	}

	clientCtx.WithNodeURI(network.TmEndpoint)
	clientCtx = clientCtx.WithClient(tmRPC)

	makerFeeRate := sdktypes.NewDecWithPrec(10, 4)        //0.0010
	takerFeeRate := sdktypes.NewDecWithPrec(100, 4)       //0.0100
	minPriceTickSize := sdktypes.NewDecWithPrec(1, 18)    //0.00010000000000000
	minQuantityTickSize := sdktypes.NewDecWithPrec(1, 18) //0.00010000000000000

	msg := &proposaltypes.SpotMarketLaunchProposal{
		Title:               "test list title",
		Description:         "test list desc",
		Ticker:              "PUG/USDT",
		BaseDenom:           "factory/inj1hdvy6tl89llqy3ze8lv6mz5qh66sx9enn0jxg6/inj12ngevx045zpvacus9s6anr258gkwpmthnz80e9",
		QuoteDenom:          "peggy0x44C21afAaF20c270EBbF5914Cfc3b5022173FEB7",
		MakerFeeRate:        &makerFeeRate,
		TakerFeeRate:        &takerFeeRate,
		MinPriceTickSize:    minPriceTickSize,
		MinQuantityTickSize: minQuantityTickSize,
	}

	chainClient, err := chainclient.NewChainClient(
		clientCtx,
		network.ChainGrpcEndpoint,
		common.OptionTLSCert(network.ChainTlsCert),
		common.OptionGasPrices("500000000inj"),
	)

	if err != nil {
		fmt.Println(err)
	}

	//AsyncBroadcastMsg, SyncBroadcastMsg, QueueBroadcastMsg
	err = chainClient.QueueBroadcastMsg(msg)

	if err != nil {
		fmt.Println(err)
	}

	time.Sleep(time.Second * 5)

	gasFee, err := chainClient.GetGasFee()

	if err != nil {
		fmt.Println(err)
		return
	}

	fmt.Println("gas fee:", gasFee, "INJ")
}
