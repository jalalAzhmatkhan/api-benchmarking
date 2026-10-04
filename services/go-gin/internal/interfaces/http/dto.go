// Package httpapi is the Gin HTTP layer: routing, request parsing, response mapping and
// error-to-status mapping. It contains no SQL and no business rules.
package httpapi

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/domain"
)

type itemRequest struct {
	Name        *string `json:"name"`
	Description *string `json:"description"`
	PriceCents  *int64  `json:"price_cents"`
	Quantity    *int64  `json:"quantity"`
}

type itemResponse struct {
	ID          int64     `json:"id"`
	Name        string    `json:"name"`
	Description *string   `json:"description"`
	PriceCents  int64     `json:"price_cents"`
	Quantity    int32     `json:"quantity"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

type errorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type errorBody struct {
	Error errorDetail `json:"error"`
}

func toResponse(it domain.Item) itemResponse {
	return itemResponse{
		ID: it.ID, Name: it.Name, Description: it.Description, PriceCents: it.PriceCents,
		Quantity: it.Quantity, CreatedAt: it.CreatedAt, UpdatedAt: it.UpdatedAt,
	}
}

func invalid(msg string) error { return &domain.ValidationError{Message: msg} }

// parseID accepts only decimal digits (no sign, no exponent, no fraction) within 1..MaxID.
func parseID(s string) (int64, error) {
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, invalid("invalid id")
		}
	}
	id, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, invalid("invalid id")
	}
	if err := domain.ValidateID(id); err != nil {
		return 0, err
	}
	return id, nil
}

// decodeInput parses the JSON body. Syntax/type problems and missing required fields are
// validation errors; unknown fields are ignored. Range rules live in the domain.
func decodeInput(r io.Reader) (domain.ItemInput, error) {
	var req itemRequest
	if err := json.NewDecoder(r).Decode(&req); err != nil {
		return domain.ItemInput{}, invalid("malformed JSON body")
	}
	if req.Name == nil {
		return domain.ItemInput{}, invalid("name is required")
	}
	if req.PriceCents == nil {
		return domain.ItemInput{}, invalid("price_cents is required")
	}
	if req.Quantity == nil {
		return domain.ItemInput{}, invalid("quantity is required")
	}
	return domain.ItemInput{
		Name: *req.Name, Description: req.Description, PriceCents: *req.PriceCents, Quantity: *req.Quantity,
	}, nil
}

// writeError maps domain errors to the contract's error body.
func writeError(c *gin.Context, err error) {
	var ve *domain.ValidationError
	switch {
	case errors.As(err, &ve):
		c.JSON(http.StatusBadRequest, errorBody{errorDetail{"VALIDATION_ERROR", ve.Message}})
	case errors.Is(err, domain.ErrNotFound):
		c.JSON(http.StatusNotFound, errorBody{errorDetail{"NOT_FOUND", "item not found"}})
	default:
		c.JSON(http.StatusInternalServerError, errorBody{errorDetail{"INTERNAL_ERROR", "internal error"}})
	}
}
