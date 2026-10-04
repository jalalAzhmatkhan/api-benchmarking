package httpapi

import (
	"context"
	"errors"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/domain"
)

// Use-case ports consumed by the handlers (implemented by the application layer).
type (
	GetItemUseCase interface {
		Execute(ctx context.Context, id int64) (domain.Item, error)
	}
	CreateItemUseCase interface {
		Execute(ctx context.Context, in domain.ItemInput) (domain.Item, error)
	}
	ReplaceItemUseCase interface {
		Execute(ctx context.Context, id int64, in domain.ItemInput) (domain.Item, error)
	}
	DeleteItemUseCase interface {
		Execute(ctx context.Context, id int64) error
	}
)

// Handler holds the four use cases.
type Handler struct {
	Get     GetItemUseCase
	Create  CreateItemUseCase
	Replace ReplaceItemUseCase
	Delete  DeleteItemUseCase
}

func (h Handler) get(c *gin.Context) {
	id, err := parseID(c.Param("id"))
	if err != nil {
		writeError(c, err)
		return
	}
	item, err := h.Get.Execute(c.Request.Context(), id)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, toResponse(item))
}

func (h Handler) create(c *gin.Context) {
	in, err := decodeInput(c.Request.Body)
	if err != nil {
		writeError(c, err)
		return
	}
	item, err := h.Create.Execute(c.Request.Context(), in)
	if err != nil {
		writeError(c, err)
		return
	}
	c.Header("Location", "/items/"+strconv.FormatInt(item.ID, 10))
	c.JSON(http.StatusCreated, toResponse(item))
}

func (h Handler) replace(c *gin.Context) {
	id, err := parseID(c.Param("id"))
	if err != nil {
		writeError(c, err)
		return
	}
	in, err := decodeInput(c.Request.Body)
	if err != nil {
		writeError(c, err)
		return
	}
	item, err := h.Replace.Execute(c.Request.Context(), id, in)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, toResponse(item))
}

func (h Handler) delete(c *gin.Context) {
	id, err := parseID(c.Param("id"))
	if err != nil {
		writeError(c, err)
		return
	}
	if err := h.Delete.Execute(c.Request.Context(), id); err != nil {
		writeError(c, err)
		return
	}
	c.Status(http.StatusNoContent)
}

// NewRouter wires the four endpoints. Release mode, no logger and no middleware except a panic
// guard that keeps the contract's 500 body (benchmark-rules.md).
func NewRouter(h Handler) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.CustomRecovery(func(c *gin.Context, _ any) {
		writeError(c, errors.New("panic"))
	}))
	r.POST("/items", h.create)
	r.GET("/items/:id", h.get)
	r.PUT("/items/:id", h.replace)
	r.DELETE("/items/:id", h.delete)
	return r
}
