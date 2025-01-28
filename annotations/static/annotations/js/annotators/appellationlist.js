var AppellationListItem = {
    props: ['appellation', 'sidebar', 'index'],
    template: `<li v-bind:class="{
						'list-group-item': true,
						'appellation-list-item': true,
						'appellation-selected': isSelected(),
						'fade-out': isDeleting
					}">
					<div v-if="error" class="error-message text-danger mb-2">
						{{ error }}
					</div>
					<div class="d-flex justify-content-between align-items-center">
						<div>
							{{ label() }}
							<div class="text-warning">
								<input v-if="sidebar == 'submitAllAppellations'" type="checkbox" v-model="checked" aria-label="...">
								Created by <strong>{{ getCreatorName(appellation.createdBy) }}</strong> on {{ getFormattedDate(appellation.created) }}
							</div>
						</div>
						
						<div class="btn-group">
							<a class="btn btn-xs btn-default" v-on:click="select" data-tooltip="Select appellation">
								<span class="glyphicon glyphicon-hand-down"></span>
							</a>
							<a class="btn btn-xs btn-default" v-on:click="toggle" v-bind:data-tooltip="appellation.visible ? 'Hide appellation' : 'Show appellation'">
								<span v-if="appellation.visible" class="glyphicon glyphicon glyphicon-eye-open"></span>
								<span v-else class="glyphicon glyphicon glyphicon-eye-close"></span>
							</a>
							<a class="btn btn-xs btn-default" @click="editAppellation" data-tooltip="Edit Appellation">
								<span class="glyphicon glyphicon-pencil"></span>
							</a>
							<a class="btn btn-xs btn-danger" 
							   @click="deleteAppellation" 
							   :disabled="isDeleting"
							   data-tooltip="Delete Appellation">
								<span class="glyphicon" 
								  :class="{'glyphicon-trash': !isDeleting, 'glyphicon-hourglass': isDeleting}">
								</span>
							</a>
						</div>
					</div>
				</li>`,
    data: function () {
        return {
            checked: true,
            canUncheckAll: false,
            canCheckAll: false,
            isDeleting: false,
            error: null
        }
    },
    mounted: function () {
        this.watchUncheckStore();
        this.watchCheckStore();
        this.$root.$on('appellationClicked', data => {
            if (data === this.appellation) {
                this.checked = !this.checked;
            }
        });
    },
    watch: {
        checked: function () {
            if (this.checked == false) {
                store.commit('removeAppellation', this.index);
                store.commit('setSelectFalse')
            } else {
                if (store.getters.getValidator == 3) {
                    store.commit('setValidator', 0);
                }
                store.commit('addAppellation', this.appellation)
                store.commit('setDeselectFalse')
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
        editAppellation() {
            // Logic
            console.log('Edit button clicked for Appellation ID:', this.appellation.id);
            this.$emit('editappellation', this.appellation);
          },
      
          deleteAppellation() {
            if (this.isDeleting) return;
            this.error = null;
            this.isDeleting = true;

            // First clear all states and stores
            if (this.appellation.selected) {
                this.appellation.selected = false;
                store.commit('setTextAppellation', []);
                store.commit('resetCreateAppelltionsToText');
                this.$root.$emit('appellationDeselected', this.appellation);
            }

            // Immediately hide and notify about deletion
            this.appellation.visible = false;
            this.$root.$emit('appellationDeleted', this.appellation);
            this.$emit('hideappellation', this.appellation);

            Appellation.delete({id: this.appellation.id})
                .then(response => {
                    // Force cleanup immediately for newly created annotations
                    this.$root.$emit('forceCleanupAppellation', this.appellation.id);
                    
                    // Remove from lists
                    store.commit('removeAppellation', this.index);
                    this.$emit('deletedappellation', this.appellation);
                })
                .catch(error => {
                    // Restore visibility on error
                    this.appellation.visible = true;
                    this.isDeleting = false;
                    this.error = error.response?.data?.detail || 'Failed to delete annotation';
                    setTimeout(() => this.error = null, 3000);
                });
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
            if (this.isDeleting) return;
            
            // Clear selection if toggling visibility
            if (this.appellation.selected) {
                this.appellation.selected = false;
                store.commit('setTextAppellation', []);
                this.$root.$emit('appellationDeselected', this.appellation);
            }
            
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
            if (this.isDeleting) return;
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
									v-on:removeAppellation="removeAppellation($event)"
									v-on:addAppellation="addAppellation($event)"
									v-for="(appellation, index) in current_appellations"
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
        handleDeletedAppellation(appellation) {
            // Remove from current_appellations immediately
            const index = this.current_appellations.findIndex(a => a.id === appellation.id);
            if (index > -1) {
                const newAppellations = [...this.current_appellations];
                newAppellations.splice(index, 1);
                this.current_appellations = newAppellations;
            }
            
            // Also update the original appellations array
            const parentIndex = this.appellations.findIndex(a => a.id === appellation.id);
            if (parentIndex > -1) {
                const newParentAppellations = [...this.appellations];
                newParentAppellations.splice(parentIndex, 1);
                this.$emit('update:appellations', newParentAppellations);
            }
        }
    }
}

// Add this CSS
const style = document.createElement('style');
style.textContent = `
    .appellation-list {
        position: relative;
    }

    .list-group-item {
        transition: all 0.3s ease;
        position: relative;
        opacity: 1;
        transform: translateY(0);
        height: auto;
        max-height: 200px; /* Adjust based on your needs */
        overflow: hidden;
    }

    .list-group-item.fade-out {
        opacity: 0;
        transform: translateY(-20px);
        max-height: 0;
        margin: 0;
        padding: 0;
        border: 0;
    }

    .appellation {
        transition: opacity 0.2s ease;
    }

    .error-message {
        font-size: 0.9em;
        margin-bottom: 8px;
        color: #dc3545;
    }

    .btn-group .btn {
        transition: all 0.2s ease;
    }

    .btn-group .btn[disabled] {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .btn-xs {
        padding: 1px 5px;
        font-size: 12px;
        line-height: 1.5;
        border-radius: 3px;
    }

    .btn-default {
        background-color: #f8f9fa;
        border-color: #ddd;
    }

    .btn-danger {
        background-color: #dc3545;
        border-color: #dc3545;
        color: white;
    }

    .btn-danger:hover:not([disabled]) {
        background-color: #c82333;
        border-color: #bd2130;
    }
`;
document.head.appendChild(style);