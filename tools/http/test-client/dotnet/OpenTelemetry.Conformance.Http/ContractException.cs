// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

namespace OpenTelemetry.Conformance.Http;

/// <summary>A server answered something the contract does not describe.</summary>
public sealed class ContractException : Exception
{
    public ContractException(string message)
        : base(message)
    {
    }

    public ContractException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
