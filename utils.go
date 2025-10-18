package main

import (
	"os"
)

// saveTextFile saves text content to a file
func saveTextFile(filename, content string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	_, err = file.WriteString(content)
	return err
}