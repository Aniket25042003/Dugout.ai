module github.com/Aniket25042003/Dugout/services/event-gateway

go 1.23

require (
	github.com/Aniket25042003/Dugout/packages/contracts/go v0.0.0-00010101000000-000000000000
	github.com/lib/pq v1.10.9
	github.com/nats-io/nats.go v1.34.1
	google.golang.org/protobuf v1.36.11
)

require (
	github.com/klauspost/compress v1.17.2 // indirect
	github.com/nats-io/nkeys v0.4.7 // indirect
	github.com/nats-io/nuid v1.0.1 // indirect
	golang.org/x/crypto v0.18.0 // indirect
	golang.org/x/sys v0.16.0 // indirect
)

replace github.com/Aniket25042003/Dugout/packages/contracts/go => ../../packages/contracts/go
