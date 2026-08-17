// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! Runner environment and lifecycle support with no OpenTelemetry dependency.

use std::env;
use std::fmt;
use std::io;

/// An environment variable required by a scenario was absent or blank.
#[derive(Debug)]
pub struct EnvironmentError {
    name: String,
}

impl fmt::Display for EnvironmentError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "required environment variable is missing: {}",
            self.name
        )
    }
}

impl std::error::Error for EnvironmentError {}

/// Returns the value of `name`, or an error that names what was missing.
///
/// # Errors
///
/// Returns [`EnvironmentError`] when the variable is absent or blank.
pub fn require(name: &str) -> Result<String, EnvironmentError> {
    env::var(name)
        .ok()
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| EnvironmentError {
            name: name.to_owned(),
        })
}

/// Blocks until standard input closes, which is how the driver says stop.
///
/// Returning from this protocol gives the scenario a chance to stop its server
/// and flush its SDK on every supported platform.
///
/// # Errors
///
/// Returns an I/O error when standard input cannot be read.
pub fn wait_for_eof() -> io::Result<()> {
    io::copy(&mut io::stdin().lock(), &mut io::sink())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::require;

    #[test]
    fn missing_environment_names_the_variable() {
        const NAME: &str = "OTEL_CONFORMANCE_RUST_TEST_MISSING";
        std::env::remove_var(NAME);

        let error = require(NAME).expect_err("the variable should be absent");

        assert!(error.to_string().contains(NAME));
    }
}
