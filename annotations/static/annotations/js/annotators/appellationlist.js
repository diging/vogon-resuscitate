var AppellationListItem = {
    props: ['appellation', 'sidebar', 'index'],
    template: `<li v-bind:class="{
						'list-group-item': true,
						'appellation-list-item': true,
						'appellation-selected': isSelected()
					}">
					
				<span class="pull-right text-muted btn-group">
					<a class="btn btn-xs" v-on:click="select" :disabled="isEditMode" data-tooltip="Select appellation">
						<span class="glyphicon glyphicon-hand-down"></span>
					</a>
					<a class="btn btn-xs" v-on:click="toggle" :disabled="isEditMode" v-bind:data-tooltip="appellation.visible ? 'Hide appellation' : 'Show appellation'">
						<span v-if="appellation.visible" class="glyphicon glyphicon glyphicon-eye-open"></span>
						<span v-else class="glyphicon glyphicon glyphicon-eye-close"></span>
					</a>
					<a class="btn btn-xs" @click="editAppellation" :disabled="isEditMode" data-tooltip="Edit appellation">
						<span class="glyphicon glyphicon-pencil"></span>
					</a>
					<a class="btn btn-xs" v-on:click="deleteAppellation" :disabled="isEditMode" data-tooltip="Delete appellation">
						<span class="glyphicon glyphicon-trash" style="color: #d9534f;"></span>
					</a>
				</span>
				
				<div v-if="deleteError" class="text-danger" style="margin-bottom: 5px;">
					{{ deleteError }}
				</div>
				
				{{ label() }}
				<div class="text-warning">
					<input v-if="sidebar == 'submitAllAppellations'" type="checkbox" v-model="checked" :disabled="isEditMode" aria-label="...">
					Created by <strong>{{ getCreatorName(appellation.createdBy) }}</strong> on {{ getFormattedDate(appellation.created) }}
				</div>
				</li>`,
    data: function () {
        return {
            checked: true,
            canUncheckAll: false,
            canCheckAll: false,
            deleteError: null,
            isEditMode: false
        }
    },
    mounted: function () {

        const id = this.appellation ? this.appellation.id : 'UNKNOWN_MOUNTING';
        console.log(`[AppellationListItem ID: ${id}] MOUNTED. Registering event listeners.`);
        // ... rest of mounted, including EventBus.$on ...
    },
    beforeDestroy() {
        const id = this.appellation ? this.appellation.id : 'UNKNOWN_DESTROYING';
        console.log(`[AppellationListItem ID: ${id}] BEFOREDESTROY. Cleaning up event listeners.`);


        this.watchUncheckStore();
        this.watchCheckStore();
        this.$root.$on('appellationClicked', data => {
            if (data === this.appellation) {
                this.checked = !this.checked;
            }

     

        this.onStartEditHandler = () => {
            console.log(`[AppellationListItem ID: ${this.appellation ? this.appellation.id : 'N/A'} event=startEdit RECEIVED] Setting this.isEditMode from ${this.isEditMode} to true`);
            this.isEditMode = true;
        };
        EventBus.$on('startEdit', this.onStartEditHandler);

        this.onCancelEditHandler = () => {
            console.log(`[AppellationListItem ID: ${this.appellation ? this.appellation.id : 'N/A'} event=cancelEdit RECEIVED] Setting this.isEditMode from ${this.isEditMode} to false`);
            this.isEditMode = false;
        };
        EventBus.$on('cancelEdit', this.onCancelEditHandler);

        this.onResetEditStateHandler = () => {
            console.log(`[AppellationListItem ID: ${this.appellation ? this.appellation.id : 'N/A'} event=resetEditState RECEIVED] Setting this.isEditMode from ${this.isEditMode} to false and clearing localStorage`);
            this.isEditMode = false;
            localStorage.removeItem('editingAppellation');
        };
        
EventBus.$on('resetEditState', this.onResetEditStateHandler);
        });
        
        // Listen for edit mode changes
        EventBus.$on('startEdit', () => {
            this.isEditMode = true;
        });
        
        EventBus.$on('cancelEdit', () => {
            this.isEditMode = false;
        });

        // Reset edit mode when a relation is created to prevent the edit button from being stuck in disabled state
        // This is necessary because creating a relation can leave appellations in an inconsistent edit state
        EventBus.$on('resetEditState', () => {
            this.isEditMode = false;
            localStorage.removeItem('editingAppellation');
        });
    },
    beforeDestroy() {
        EventBus.$off('startEdit');
        EventBus.$off('cancelEdit');
        EventBus.$off('resetEditState');
        this.$root.$off('appellationUpdated', this.updateAppellation);
    },
    watch: {
        // Instead of removing from the array when unchecked,
        // we just set `.selected = false`.
        checked(newVal) {
          if (!newVal) {
            // Unselect it without removing from the array
            this.appellation.selected = false;
          } else {
            // Mark it selected
            this.appellation.selected = true;
          }
        },
        
      },
    methods: {
        watchUncheckStore: function () {
            store.watch(
                (state) => {
                    return store.getters.getDeselect
                },
                (val) => {
                    if (val) {
                        this.uncheckAll()
                        this.canCheckAll = true;
                    }
                },
            );
        },
        watchCheckStore: function () {
            store.watch(
                (state) => {
                    return store.getters.getSelect
                },
                (val) => {
                    if (val) {
                        this.checkAll()
                    }
                },
            );
        },

        uncheckAll: function () {
            this.checked = false;
        },
        checkAll: function () {
            this.checked = true;
        },
        hide: function () {
            this.$emit("hideappellation", this.appellation);
        },
        show: function () {
            this.$emit("showappellation", this.appellation);
        },
        toggle: function () {
            if (this.appellation.visible) {
                this.hide();
            } else {
                this.show();
            }
        },
        isSelected: function () {
            return this.appellation.selected;
        },
        select: function () {
            this.$emit('selectappellation', this.appellation);
        },
        label: function () {
            if (this.appellation.interpretation) {
                return this.appellation.interpretation.label;
            } else if (this.appellation.dateRepresentation) {
                return this.appellation.dateRepresentation;
            }
        },
        getCreatorName: function (creator) {
            if (creator.id == USER_ID) {
                return 'you';
            } else {
                return creator.username;
            }
        },
        getFormattedDate: function (isodate) {
            return moment(isodate).format('dddd LL [at] LT');
        },
        deleteAppellation: function() {
            this.deleteError = null;
            const deletedAppId = this.appellation.id; 

            Appellation.delete({id: deletedAppId}).then(response => {
                this.$emit('removeappellation', this.appellation); 

                const editingAppData = localStorage.getItem('editingAppellation');
                let isDeletingTheEditedItem = false;
                if (editingAppData) {
                    try {
                        const editingApp = JSON.parse(editingAppData);
                        if (editingApp && editingApp.id === deletedAppId) {
                            isDeletingTheEditedItem = true;
                        }
                    } catch (e) {
                        console.error("Error parsing editingAppellation from localStorage:", e);
                        isDeletingTheEditedItem = true; // Be safe, assume reset if data corrupted
                    }
                }

                if (isDeletingTheEditedItem) {

                    EventBus.$emit('resetEditState');
                } else {

                    // 'cancelEdit' resets isEditMode without clearing localStorage for the other edit.
                    EventBus.$emit('cancelEdit');
                }
                
            }).catch(error => {
                if (error.status === 400) {
                    this.deleteError = "This annotation is used in a relation and cannot be deleted.";
                } else {
                    this.deleteError = "Error deleting annotation. Please try again later.";
                }
            });
        },

    editAppellation() {
        console.log(`[AppellationListItem ID: ${this.appellation.id}] editAppellation CALLED. Current isEditMode: ${this.isEditMode}. localStorage:`, localStorage.getItem('editingAppellation'));


        /*
        if (this.isEditMode) {
            const editingAppData = localStorage.getItem('editingAppellation');
            let currentEditingAppIdInStorage = null;
            if (editingAppData) {
                try {
                    currentEditingAppIdInStorage = JSON.parse(editingAppData).id;
                } catch (e) { console.error("Error parsing localStorage in editAppellation guard:", e); }
            }

            if (currentEditingAppIdInStorage === this.appellation.id) {
                console.log(`[AppellationListItem ID: ${this.appellation.id}] GUARD: isEditMode is true, localStorage matches. Re-showing message.`);
                EventBus.$emit('showMessage', {
                    text: 'Please select the new text position. Press ESC to cancel.',
                    type: 'info'
                });
            } else {
                console.log(`[AppellationListItem ID: ${this.appellation.id}] GUARD: isEditMode is true, but localStorage is for item ${currentEditingAppIdInStorage} or empty. Aborting edit.`);
                EventBus.$emit('showMessage', {
                    text: 'Another annotation is currently being edited. Please complete or cancel that edit first.',
                    type: 'warning',
                    duration: 3000
                });
            }
            return; 
        }
        */
        
        console.log(`[AppellationListItem ID: ${this.appellation.id}] editAppellation: Proceeding PAST initial guard (or guard is commented out).`);
        localStorage.setItem('editingAppellation', JSON.stringify(this.appellation));
        console.log(`[AppellationListItem ID: ${this.appellation.id}] editAppellation: localStorage.editingAppellation set to:`, JSON.parse(localStorage.getItem('editingAppellation')));
        
        this.appellation.selected = false; 

        
        EventBus.$emit('startEdit'); 
        console.log(`[AppellationListItem ID: ${this.appellation.id}] editAppellation: Emitted startEdit.`);
        
        EventBus.$emit('showMessage', {
            text: 'Please select the new text position. Press ESC to cancel.',
            type: 'info'
        });
        console.log(`[AppellationListItem ID: ${this.appellation.id}] editAppellation: Emitted showMessage.`);
    }

    }
}


AppellationList = {
    props: ['appellations', 'sidebar'],
    template: `
				<div>
					<div style="float: left; margin-left: 3%;">
						<h4  v-if="error_message" style="color: red;">{{ error_message }}</h4>
					</div>
					<div class="row">
						<div class="col-lg-8 col-xl-8">
							<h5 style="padding-left: 5%;" v-if="conceptLabel">Concept: {{ conceptLabel }}</h5>
						</div>
						<div class="text-right col-lg-4 col-xl-4">
							<a v-if="allHidden()" v-on:click="showAll" class="btn">
								Show all
							</a>
							<a v-on:click="hideAll" class="btn">
								Hide all
							</a>
						</div>
					</div>
					<div>
						<div style="padding: 0%;" class="col-lg-12 col-xl-2" v-if="sidebar == 'submitAllAppellations'">
							<button v-bind:style="[calcSizeOfPage ? {float: 'right', 'margin-right': 3 + '%'} : {float: 'left', 'margin-left': 3 + '%'}]"   @click="deselectAllTemplatesRef()" class="btn btn-default btn-sm" v-tooltip="'Deselect All'"><span class="glyphicon glyphicon-remove-sign"></span></button>
							<button v-bind:style="[calcSizeOfPage ? {float: 'right', 'margin-right': 3 + '%'} : {float: 'left', 'margin-left': 3 + '%', 'margin-bottom': 3 + '%'}]"  @click="checkAll()" class="btn btn-default btn-sm" v-tooltip="'Select All'"><span class="glyphicon glyphicon-ok-sign"></span></button>
						</div>
						<div style="margin-bottom: 2%;" v-if="sidebar == 'submitAllAppellations'" >
							<div style="padding-right: 0%; padding-left: 0%; margin-left: 1%;" class="col-xl-6">
								<select class="btn btn-default dropdown-toggle"  v-if="sidebar == 'submitAllAppellations'" v-model="selected_template" style="float: left; margin-left: 2.5%; width: 100%;">
									<option value=0>Please select Relationship</option>
									<option v-for="template in templates" :value=template>{{ template.name }} - <span style="color: lightgrey;">{{ template.description }}</span></option>
								</select>
							</div>
							<div class="col-lg-12 col-xl-3" v-bind:style="[calcSizeOfPage ? {} : {'padding-left': 3.25 + '%'}]">
								<button v-if="!conceptLabel" v-bind:style="[calcSizeOfPage ? {'margin-top': 1 + '%'} : {'margin-top': 2 + '%', 'margin-bottom': 3 + '%'}]" @click="selectConcept()" class="btn btn-info btn-xs" >Select Text Concept</button>
							</div>
						</div>
						<div class="col-lg-12 col-xl-12" style="padding-left: 2.5%; padding-right: 1%">
							<ul class="list-group appellation-list" style="max-height: 400px; margin-top: 2%;">
								<appellation-list-item
									v-bind:sidebar="sidebar"
									v-on:hideappellation="hideAppellation"
									v-on:showappellation="showAppellation"
									v-on:selectappellation="selectAppellation"
                                    v-on:addAppellation="addAppellation($event)"
									v-on:removeappellation="removeAppellation"
									v-for="(appellation, index) in current_appellations"
                                    :key="appellation.id"
									v-bind:appellation=appellation
									v-if="appellation != null"
									v-bind:index="index">
								</appellation-list-item>
							</ul>
						</div>
					</div>
				</div>
			   `,
    components: {
        'appellation-list-item': AppellationListItem,
    },
    data: function () {
        return {
            current_appellations: this.appellations,
            selected_template: null,
            templates: null,
            appellations_to_submit: [],
            error_message: "",
        }
    },
    computed: {
        conceptLabel: function () {
            return store.getters.conceptLabel
        },
        calcSizeOfPage: function () {
            let width = $(document).width();
            if (width >= 2000) {
                return true
            } else {
                return false
            }
        }
    },
    created: function () {
        this.getTemplates();
        store.commit('setAppellations', this.appellations);
        this.watchStoreForValidator();
    },
    watch: {
        appellations: function (value) {
            // Replace an array prop wholesale doesn't seem to trigger a
            //  DOM update in the v-for binding, but a push() does; so we'll
            //  just push the appellations that aren't already in the array.
            this.current_appellations = this.appellations;
        },
        selected_template: function () {
            store.commit("setTemplate", this.selected_template);
            if (store.getters.getValidator == 1) {
                store.commit('setValidator', 0)
            }
        },
    },
    methods: {
        /*************************************************
         * Start Methods to create relationships to text *
         *************************************************/
        selectConcept: function () {
            store.commit('triggerConcepts')
        },
        getTemplates: function () {
            RelationTemplateResource.get_single_relation().then(response => {
                this.templates = response.body;
            }).catch(function (error) {
                console.log('Failed to get relationtemplates', error);
            });
        },
        getTemplateFields: function () {
            RelationTemplateResource.query({
                search: this.selected_template,
                format: "json",
                all: false
            }).then(function (response) {
                store.commit("setTemplate", response.body.templates[0]);
            }).catch(function (error) {
                console.log('Failed to get relationtemplates', error);
                self.searching = false;
            });
        },
        deselectAllTemplatesRef: function () {
            store.commit('deselect');
        },
        checkAll: function () {
            store.commit('selectAll');
        },
        watchStoreForValidator: function () {
            store.watch(
                (state) => {
                    return store.getters.getValidator;
                },
                (val) => {
                    switch (val) {
                        case 0:
                            this.error_message = "";
                            break;
                        case 1:
                            this.error_message = "Please Select A Template";
                            break;
                        case 2:
                            this.error_message = "Please Select A Concept";
                            break;
                        case 3:
                            this.error_message = "Please Select At Least One Appellation";
                            break;
                    }
                },
            );
        },
        /***********************************************
         * End Methods to create relationships to text *
         ***********************************************/
        allHidden: function () {
            var ah = true;
            this.appellations.forEach(function (appellation) {
                if (appellation.visible) ah = false;
            });
            return ah;
        },
        hideAll: function () {
            this.$emit("hideallappellations");
        },
        showAll: function () {
            this.$emit("showallappellations");
        },
        hideAppellation: function (appellation) {
            this.$emit("hideappellation", appellation);
        },
        showAppellation: function (appellation) {
            this.$emit("showappellation", appellation);
        },
        selectAppellation: function (appellation) {
            this.$emit('selectappellation', appellation);
        },
        removeAppellation: function(appellation) {
            // Remove from current_appellations array
            const index = this.current_appellations.indexOf(appellation);
            if (index > -1) {
                this.current_appellations.splice(index, 1);
            }
            // Emit to parent to remove from text display
            this.$emit('removeappellation', appellation);
        },
        /*
         * Updates an appellation in the current_appellations array
         * @param updatedAppellation - The new appellation data to update with
         * 
         * This function:
         * 1. Finds the appellation to update by matching IDs
         * 2. Creates a new array to maintain reactivity
         * 3. Replaces the old appellation with the updated one
         * 4. Assigns the new array back to current_appellations
         */
        updateAppellation: function(updatedAppellation) {
            const index = this.current_appellations.findIndex(a => a.id === updatedAppellation.id);
            if (index !== -1) {
                // Create a new array with the updated appellation
                const newAppellations = [...this.current_appellations];
                newAppellations[index] = updatedAppellation;
                this.current_appellations = newAppellations;
            }
        }
    },
}