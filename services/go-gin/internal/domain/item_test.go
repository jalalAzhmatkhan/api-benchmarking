package domain

import (
	"errors"
	"strings"
	"testing"
)

func str(s string) *string { return &s }

func TestValidateID(t *testing.T) {
	for _, id := range []int64{1, 100001, MaxID} {
		if err := ValidateID(id); err != nil {
			t.Errorf("ValidateID(%d) = %v, want nil", id, err)
		}
	}
	for _, id := range []int64{0, -1, MaxID + 1} {
		var ve *ValidationError
		if err := ValidateID(id); !errors.As(err, &ve) {
			t.Errorf("ValidateID(%d) = %v, want *ValidationError", id, err)
		}
	}
}

func TestItemInputValidate(t *testing.T) {
	valid := ItemInput{Name: "Widget", Description: str("Blue"), PriceCents: 1999, Quantity: 5}
	tests := []struct {
		name    string
		mutate  func(*ItemInput)
		wantErr bool
	}{
		{"valid", func(*ItemInput) {}, false},
		{"description nil", func(i *ItemInput) { i.Description = nil }, false},
		{"description empty", func(i *ItemInput) { i.Description = str("") }, false},
		{"description 1000", func(i *ItemInput) { i.Description = str(strings.Repeat("d", 1000)) }, false},
		{"description 1001", func(i *ItemInput) { i.Description = str(strings.Repeat("d", 1001)) }, true},
		{"description 1000 multibyte", func(i *ItemInput) { i.Description = str(strings.Repeat("é", 1000)) }, false},
		{"name empty", func(i *ItemInput) { i.Name = "" }, true},
		{"name 1", func(i *ItemInput) { i.Name = "a" }, false},
		{"name 100", func(i *ItemInput) { i.Name = strings.Repeat("a", 100) }, false},
		{"name 101", func(i *ItemInput) { i.Name = strings.Repeat("a", 101) }, true},
		{"name 100 multibyte", func(i *ItemInput) { i.Name = strings.Repeat("é", 100) }, false},
		{"price 0", func(i *ItemInput) { i.PriceCents = 0 }, false},
		{"price max", func(i *ItemInput) { i.PriceCents = MaxPriceCents }, false},
		{"price negative", func(i *ItemInput) { i.PriceCents = -1 }, true},
		{"price above max", func(i *ItemInput) { i.PriceCents = MaxPriceCents + 1 }, true},
		{"quantity 0", func(i *ItemInput) { i.Quantity = 0 }, false},
		{"quantity max", func(i *ItemInput) { i.Quantity = MaxQuantity }, false},
		{"quantity negative", func(i *ItemInput) { i.Quantity = -1 }, true},
		{"quantity above max", func(i *ItemInput) { i.Quantity = MaxQuantity + 1 }, true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			in := valid
			tc.mutate(&in)
			err := in.Validate()
			var ve *ValidationError
			if tc.wantErr {
				if !errors.As(err, &ve) {
					t.Fatalf("Validate() = %v, want *ValidationError", err)
				}
				if ve.Error() == "" {
					t.Fatal("ValidationError message is empty")
				}
				return
			}
			if err != nil {
				t.Fatalf("Validate() = %v, want nil", err)
			}
		})
	}
}
