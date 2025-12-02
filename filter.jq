( [ .Results[].Misconfigurations[] | select(.Severity == "HIGH") | {Description: .Description, CVSSv3: .AVD_ID, Severity: .Severity} ] )
