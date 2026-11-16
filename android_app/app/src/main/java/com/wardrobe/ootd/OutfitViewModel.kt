package com.wardrobe.ootd

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class OutfitState(
    val outfits: List<Outfit>? = null,
    val error: String? = null,
    val unauthorized: Boolean = false,
    val selected: Outfit? = null,
    val confirmDelete: Boolean = false,
    val saving: Boolean = false,
    val detailError: String? = null,
    val building: Boolean = false,
    val pickable: List<Item> = emptyList(),
    val picked: Set<Int> = emptySet(),
    val builderName: String = "",
    val builderError: String? = null,
    val wearNotice: String? = null,
)

class OutfitViewModel(private val api: Api) : ViewModel() {
    var state by mutableStateOf(OutfitState())
        private set

    fun start() {
        state = state.copy(error = null)
        viewModelScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { api.outfits() }
                state = state.copy(outfits = result, error = null)
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(error = e.message ?: "Could not load your outfits")
            }
        }
    }

    fun consumeUnauthorized() { state = state.copy(unauthorized = false) }

    fun setWearNotice(value: String?) { state = state.copy(wearNotice = value) }

    fun open(outfit: Outfit) {
        state = state.copy(selected = outfit, confirmDelete = false, detailError = null)
        viewModelScope.launch {
            try {
                val detail = withContext(Dispatchers.IO) { api.outfit(outfit.id) }
                if (state.selected?.id == outfit.id) state = state.copy(selected = detail)
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(detailError = e.message ?: "Could not load this outfit")
            }
        }
    }

    fun close() { state = state.copy(selected = null, confirmDelete = false, detailError = null) }
    fun askDelete() { if (!state.saving) state = state.copy(confirmDelete = true) }
    fun cancelDelete() { state = state.copy(confirmDelete = false) }

    fun delete() {
        val selected = state.selected ?: return
        if (state.saving) return
        state = state.copy(saving = true, confirmDelete = false, detailError = null)
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) { api.deleteOutfit(selected.id) }
                state = state.copy(
                    outfits = state.outfits?.filterNot { it.id == selected.id },
                    selected = null,
                )
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true, detailError = "Session expired")
            } catch (e: Exception) {
                state = state.copy(detailError = e.message ?: "Could not delete this outfit")
            } finally {
                state = state.copy(saving = false)
            }
        }
    }

    fun openBuilder() {
        if (state.saving) return
        state = state.copy(building = true, pickable = emptyList(), picked = emptySet(), builderName = "", builderError = null)
        viewModelScope.launch {
            try {
                val items = withContext(Dispatchers.IO) { api.items("all", "") }
                if (state.building) state = state.copy(pickable = items)
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(builderError = e.message ?: "Could not load your closet")
            }
        }
    }

    fun cancelBuilder() {
        if (!state.saving) state = state.copy(building = false, builderError = null)
    }

    fun toggle(itemId: Int) {
        val picked = state.picked
        if (itemId in picked) {
            state = state.copy(picked = picked - itemId, builderError = null)
        } else if (picked.size >= 8) {
            state = state.copy(builderError = "Pick up to 8 pieces.")
        } else {
            state = state.copy(picked = picked + itemId, builderError = null)
        }
    }

    fun editBuilderName(value: String) { state = state.copy(builderName = value, builderError = null) }

    fun save() {
        if (state.saving) return
        val name = state.builderName.trim()
        val itemIds = state.picked.toList()
        if (name.isBlank()) {
            state = state.copy(builderError = "Enter a name for this outfit.")
            return
        }
        if (itemIds.isEmpty()) {
            state = state.copy(builderError = "Pick at least one piece.")
            return
        }
        state = state.copy(saving = true, builderError = null)
        viewModelScope.launch {
            try {
                val saved = withContext(Dispatchers.IO) { api.createOutfit(name, itemIds) }
                state = state.copy(outfits = listOf(saved) + state.outfits.orEmpty(), building = false)
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true, builderError = "Session expired")
            } catch (e: Exception) {
                state = state.copy(builderError = e.message ?: "Could not save this outfit")
            } finally {
                state = state.copy(saving = false)
            }
        }
    }
}

class OutfitViewModelFactory(private val api: Api) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(OutfitViewModel::class.java)) return OutfitViewModel(api) as T
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
