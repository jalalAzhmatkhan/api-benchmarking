package application

import (
	"context"
	"errors"
	"testing"

	"github.com/jalalAzhmatkhan/api-benchmarking/services/go-gin/internal/domain"
)

type fakeRepo struct {
	calls int
	item  domain.Item
	err   error
	gotID int64
	gotIn domain.ItemInput
}

func (f *fakeRepo) Get(_ context.Context, id int64) (domain.Item, error) {
	f.calls++
	f.gotID = id
	return f.item, f.err
}

func (f *fakeRepo) Create(_ context.Context, in domain.ItemInput) (domain.Item, error) {
	f.calls++
	f.gotIn = in
	return f.item, f.err
}

func (f *fakeRepo) Replace(_ context.Context, id int64, in domain.ItemInput) (domain.Item, error) {
	f.calls++
	f.gotID, f.gotIn = id, in
	return f.item, f.err
}

func (f *fakeRepo) Delete(_ context.Context, id int64) error {
	f.calls++
	f.gotID = id
	return f.err
}

var (
	ctx     = context.Background()
	okInput = domain.ItemInput{Name: "n", PriceCents: 1, Quantity: 1}
	badIn   = domain.ItemInput{Name: "", PriceCents: 1, Quantity: 1}
)

func isValidation(err error) bool {
	var ve *domain.ValidationError
	return errors.As(err, &ve)
}

func TestGetItem(t *testing.T) {
	repo := &fakeRepo{item: domain.Item{ID: 7}}
	got, err := GetItem{repo}.Execute(ctx, 7)
	if err != nil || got.ID != 7 || repo.gotID != 7 {
		t.Fatalf("got %+v, %v", got, err)
	}
	repo = &fakeRepo{}
	if _, err := (GetItem{repo}).Execute(ctx, 0); !isValidation(err) || repo.calls != 0 {
		t.Fatalf("invalid id must fail before the repository: %v (calls=%d)", err, repo.calls)
	}
	repo = &fakeRepo{err: domain.ErrNotFound}
	if _, err := (GetItem{repo}).Execute(ctx, 1); !errors.Is(err, domain.ErrNotFound) {
		t.Fatalf("repository error must propagate: %v", err)
	}
}

func TestCreateItem(t *testing.T) {
	repo := &fakeRepo{item: domain.Item{ID: 100001}}
	got, err := CreateItem{repo}.Execute(ctx, okInput)
	if err != nil || got.ID != 100001 || repo.gotIn.Name != "n" {
		t.Fatalf("got %+v, %v", got, err)
	}
	repo = &fakeRepo{}
	if _, err := (CreateItem{repo}).Execute(ctx, badIn); !isValidation(err) || repo.calls != 0 {
		t.Fatalf("invalid input must fail before the repository: %v (calls=%d)", err, repo.calls)
	}
	boom := errors.New("boom")
	repo = &fakeRepo{err: boom}
	if _, err := (CreateItem{repo}).Execute(ctx, okInput); !errors.Is(err, boom) {
		t.Fatalf("repository error must propagate: %v", err)
	}
}

func TestReplaceItem(t *testing.T) {
	repo := &fakeRepo{item: domain.Item{ID: 5}}
	got, err := ReplaceItem{repo}.Execute(ctx, 5, okInput)
	if err != nil || got.ID != 5 || repo.gotID != 5 {
		t.Fatalf("got %+v, %v", got, err)
	}
	repo = &fakeRepo{}
	if _, err := (ReplaceItem{repo}).Execute(ctx, -1, okInput); !isValidation(err) || repo.calls != 0 {
		t.Fatalf("invalid id: %v (calls=%d)", err, repo.calls)
	}
	if _, err := (ReplaceItem{repo}).Execute(ctx, 1, badIn); !isValidation(err) || repo.calls != 0 {
		t.Fatalf("invalid input: %v (calls=%d)", err, repo.calls)
	}
	repo = &fakeRepo{err: domain.ErrNotFound}
	if _, err := (ReplaceItem{repo}).Execute(ctx, 1, okInput); !errors.Is(err, domain.ErrNotFound) {
		t.Fatalf("repository error must propagate: %v", err)
	}
}

func TestDeleteItem(t *testing.T) {
	repo := &fakeRepo{}
	if err := (DeleteItem{repo}).Execute(ctx, 9); err != nil || repo.gotID != 9 {
		t.Fatalf("got %v", err)
	}
	repo = &fakeRepo{}
	if err := (DeleteItem{repo}).Execute(ctx, 0); !isValidation(err) || repo.calls != 0 {
		t.Fatalf("invalid id must fail before the repository: %v (calls=%d)", err, repo.calls)
	}
	repo = &fakeRepo{err: domain.ErrNotFound}
	if err := (DeleteItem{repo}).Execute(ctx, 1); !errors.Is(err, domain.ErrNotFound) {
		t.Fatalf("repository error must propagate: %v", err)
	}
}
